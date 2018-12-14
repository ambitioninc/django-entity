"""
Shared utilities for database operations
"""
from collections import namedtuple
import datetime as dt

from django.db import connection, models


def _quote(field):
    return '"{0}"'.format(field)


def _get_update_fields(model, uniques, to_update):
    """The fields to be updated in an upsert

    Always exclude auto_now_add, id, and unique fields in an update
    """
    if to_update is None:
        exclude = ['id'] + list(uniques)
        to_update = [
            field.attname for field in model._meta.fields
            if field.attname not in exclude and not getattr(field, 'auto_now_add', False)
        ]

    return to_update


def _fill_auto_fields(model, values):
    """
    Given a list of models, fill in auto_now and auto_now_add fields
    for upserts. Since django manager utils passes Djagno's ORM, these values
    have to be automatically constructed
    """
    auto_field_names = [
        f.attname
        for f in model._meta.fields
        if getattr(f, 'auto_now', False) or getattr(f, 'auto_now_add', False)
    ]
    now = dt.datetime.now(dt.timezone.utc)
    for value in values:
        for f in auto_field_names:
            setattr(value, f, now)

    return values


def _sort_by_unique_fields(values, unique_fields):
    """Sort a list of models by their unique fields

    Sorting models in an upsert greatly reduces the chances of deadlock
    when doing concurrent upserts
    """
    def sort_key(val):
        return tuple(getattr(val, f) for f in unique_fields)
    return sorted(values, key=sort_key)


class UpsertQuery:
    """
    A helper class for perfoming an upsert
    """
    def __init__(self, qset, rows, unique_fields, update_fields=None, returning=True, sync=False):
        self.qset = qset if isinstance(qset, models.QuerySet) else qset.objects.all()
        self.model = self.qset.model
        # Populate automatically generated fields in the rows like date times
        _fill_auto_fields(self.model, rows)
        # Sort the rows to reduce the chances of deadlock during concurrent upserts
        self.rows = _sort_by_unique_fields(rows, unique_fields)
        self.unique_fields = unique_fields
        self.update_fields = _get_update_fields(self.model, unique_fields, update_fields)
        self.sync = sync
        self.returning = returning
        if self.sync and self.returning is not True:
            self.returning = set(self.returning) if self.returning else set()
            self.returning.add('id')

    def get_upsert_sql(self):  # pylint: disable=too-many-locals
        """
        Generates the postgres specific sql necessary to perform an upsert (ON CONFLICT)
        INSERT INTO table_name (field1, field2)
        VALUES (1, 'two')
        ON CONFLICT (unique_field) DO UPDATE SET field2 = EXCLUDED.field2;
        """
        # Use all fields except pk unless the uniqueness constraint is the pk field
        all_fields = [
            field for field in self.model._meta.fields
            if field.column != self.model._meta.pk.name
        ]

        all_field_names = [field.column for field in all_fields]
        all_field_names_sql = ', '.join([_quote(field) for field in all_field_names])

        # Convert field names to db column names
        unique_fields = [
            self.model._meta.get_field(unique_field)
            for unique_field in self.unique_fields
        ]
        update_fields = [
            self.model._meta.get_field(update_field)
            for update_field in self.update_fields
        ]

        unique_field_names_sql = ', '.join([
            _quote(field.column) for field in unique_fields
        ])
        update_fields_sql = ', '.join([
            '{0} = EXCLUDED.{0}'.format(_quote(field.column))
            for field in update_fields
        ])

        row_values = []
        sql_args = []

        for row in self.rows:
            placeholders = []
            for field in all_fields:
                # Convert field value to db value
                # Use attname here to support fields with custom db_column names
                sql_args.append(field.get_db_prep_save(getattr(row, field.attname),
                                                       connection))
                placeholders.append('%s')
            row_values.append('({0})'.format(', '.join(placeholders)))
        row_values_sql = ', '.join(row_values)

        return_sql = ''
        if self.returning:
            action_sql = ', (xmax = 0) AS inserted_'
            if self.returning is True:
                return_sql = 'RETURNING * {action_sql}'.format(action_sql=action_sql)
            else:
                return_fields_sql = ', '.join(_quote(field) for field in self.returning)
                return_sql = 'RETURNING {return_fields_sql} {action_sql}'.format(return_fields_sql=return_fields_sql,
                                                                                 action_sql=action_sql)

        if update_fields:
            sql = (
                'INSERT INTO {0} ({1}) VALUES {2} ON CONFLICT ({3}) DO UPDATE SET {4} {5}'
            ).format(
                self.model._meta.db_table,
                all_field_names_sql,
                row_values_sql,
                unique_field_names_sql,
                update_fields_sql,
                return_sql
            )
        else:
            sql = (
                'INSERT INTO {0} ({1}) VALUES {2} ON CONFLICT ({3}) {4} {5}'
            ).format(
                self.model._meta.db_table,
                all_field_names_sql,
                row_values_sql,
                unique_field_names_sql,
                'DO UPDATE SET {0}=EXCLUDED.{0}'.format(unique_fields[0].column),
                return_sql
            )

        return sql, sql_args

    def fetch_all(self):
        """Do an upsert"""
        upserted = []
        deleted = []
        if self.rows:
            sql, sql_args = self.get_upsert_sql()
            with connection.cursor() as cursor:
                cursor.execute(sql, sql_args)
                if cursor.description:
                    nt_result = namedtuple('Result', [col[0] for col in cursor.description])
                    upserted = [nt_result(*row) for row in cursor.fetchall()]

        if self.sync:
            orig_ids = frozenset(self.qset.values_list('id', flat=True))
            deleted = list(orig_ids - frozenset([r.id for r in upserted]))
            self.model.objects.filter(pk__in=deleted).delete()

        nt_deleted_result = namedtuple('DeletedResult', ['id'])
        return (
            [r for r in upserted if r.inserted_],
            [r for r in upserted if not r.inserted_],
            [nt_deleted_result(id=d) for d in deleted]
        )


def upsert(queryset, model_objs, unique_fields,
           update_fields=None, returning=False, sync=False):
    """Does a bulk upsert on a table.

    table (Model|QuerySet): A table or a queryset that defines the collection to sync
    collection (List[Model]): A list of Django models to sync. All models in this list
        will be bulk upserted and any models not in the table (or queryset) will be deleted.
    uniques (List[str]): A list of fields that define the uniqueness of the model
    to_update (List[str], default=None): A list of fields to update whenever objects
        already exist. If an empty list is provided, it is equivalent to doing a bulk
        insert on the objects that dont exist. If `None`, all fields will be updated.
    returning (bool|List[str]): If True, returns all fields. If a list, only returns
        fields in the list
    sync (bool, default=False): Perform a sync operation on the queryset
    """
    q = UpsertQuery(queryset, model_objs, unique_fields, update_fields,
                    returning=returning, sync=sync)
    return q.fetch_all()
