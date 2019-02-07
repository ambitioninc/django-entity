"""
Provides functions for syncing entities and their relationships to the
Entity and EntityRelationship tables.
"""
import logging
import sys

import wrapt
from collections import defaultdict
from itertools import chain

from django.contrib.contenttypes.models import ContentType
import manager_utils
from django.db import transaction, connection

from entity.config import entity_registry
from entity.models import Entity, EntityRelationship, EntityKind


LOG = logging.getLogger(__name__)


@wrapt.decorator
def defer_entity_syncing(wrapped, instance, args, kwargs):
    """
    A decorator that can be used to defer the syncing of entities until after the method has been run
    This is being introduced to help avoid deadlocks in the meantime as we attempt to better understand
    why they are happening
    """

    # Defer entity syncing while we run our method
    sync_entities.defer = True

    # Run the method
    try:
        return wrapped(*args, **kwargs)

    # After we run the method disable the deferred syncing
    # and sync all the entities that have been buffered to be synced
    finally:
        # Enable entity syncing again
        sync_entities.defer = False

        # Get the models that need to be synced
        model_objs = list(sync_entities.buffer.values())

        # If none is in the model objects we need to sync all
        if None in model_objs:
            model_objs = list()

        # Clear the buffer
        sync_entities.buffer = {}

        # Sync the entities that were deferred
        sync_entities(*model_objs)


class SyncLock(object):
    """
    This will create a postgres advisory lock to be used during the syncing process
    This is being introduced to help avoid deadlocks in the meantime as we attempt to better understand
    why they are happening
    """
    def __init__(self, model, name):
        # Save the model
        self._model = model

        # Save the name
        self._name = name

        # Create an empty transaction
        self._transaction = None

        # Call the parent
        super(SyncLock, self).__init__()

    def __enter__(self):
        # Create the transaction
        self._transaction = transaction.atomic()

        lock_sql = (
            'SELECT '
            'pg_advisory_xact_lock(\'{table_name}\'::regclass::integer, hashtext(\'{lock_name}\'));'
        ).format(
            table_name=self._model._meta.db_table,
            lock_name=self._name
        )

        # Start the transaction
        self._transaction.__enter__()

        # Keep a reference to the exception
        exception = None

        # Create the connection
        try:
            with connection.cursor() as cursor:
                cursor.execute(lock_sql)
        except Exception as e:
            exception = e

        # If we have an exception, raise it
        if exception is not None:
            self.__exit__(*sys.exc_info())
            raise exception

        # Return the transaction
        return transaction

    def __exit__(self, *args, **kwargs):
        # Exit the transaction
        try:
            if self._transaction:
                self._transaction.__exit__(*args, **kwargs)
        except:
            pass


def _get_super_entities_by_ctype(model_objs_by_ctype, model_ids_to_sync, sync_all):
    """
    Given model objects organized by content type and a dictionary of all model IDs that need
    to be synced, organize all super entity relationships that need to be synced.

    Ensure that the model_ids_to_sync dict is updated with any new super entities
    that need to be part of the overall entity sync
    """
    super_entities_by_ctype = defaultdict(lambda: defaultdict(list))  # pragma: no cover
    for ctype, model_objs_for_ctype in model_objs_by_ctype.items():
        entity_config = entity_registry.entity_registry.get(ctype.model_class())
        super_entities = entity_config.get_super_entities(model_objs_for_ctype, sync_all)
        super_entities_by_ctype[ctype] = {
            ContentType.objects.get_for_model(model_class, for_concrete_model=False): relationships
            for model_class, relationships in super_entities.items()
        }

        # Continue adding to the set of entities that need to be synced
        for super_entity_ctype, relationships in super_entities_by_ctype[ctype].items():
            for sub_entity_id, super_entity_id in relationships:
                model_ids_to_sync[ctype].add(sub_entity_id)
                model_ids_to_sync[super_entity_ctype].add(super_entity_id)

    return super_entities_by_ctype


def _get_model_objs_to_sync(model_ids_to_sync, model_objs_map, sync_all):
    """
    Given the model IDs to sync, fetch all model objects to sync
    """
    model_objs_to_sync = {}
    for ctype, model_ids_to_sync_for_ctype in model_ids_to_sync.items():
        model_qset = entity_registry.entity_registry.get(ctype.model_class()).queryset

        if not sync_all:
            model_objs_to_sync[ctype] = model_qset.filter(id__in=model_ids_to_sync_for_ctype)
        else:
            model_objs_to_sync[ctype] = [
                model_objs_map[ctype, model_id] for model_id in model_ids_to_sync_for_ctype
            ]

    return model_objs_to_sync


def sync_entities(*model_objs):
    """
    Syncs entities

    Args:
        model_objs (List[Model]): The model objects to sync. If empty, all entities will be synced
    """

    # Check if we are deferring processing
    if sync_entities.defer:
        # If we dont have any model objects passed add a none to let us know that we need to sync all
        if not model_objs:
            sync_entities.buffer[None] = None
        else:
            # Add each model obj to the buffer
            for model_obj in model_objs:
                sync_entities.buffer[(model_obj.__class__, model_obj.pk)] = model_obj

        # Return false that we did not do anything
        return False

    # Log what we are syncing
    LOG.debug('sync_entities')
    LOG.debug(model_objs)

    # Determine if we are syncing all
    sync_all = not model_objs
    model_objs_map = {
        (ContentType.objects.get_for_model(model_obj, for_concrete_model=False), model_obj.id): model_obj
        for model_obj in model_objs
    }
    if not model_objs_map:
        # Sync everything
        for model_class, entity_config in entity_registry.entity_registry.items():
            model_qset = entity_config.queryset
            model_objs_map.update({
                (ContentType.objects.get_for_model(model_class, for_concrete_model=False), model_obj.id): model_obj
                for model_obj in model_qset.all()
            })

    # Organize by content type
    model_objs_by_ctype = defaultdict(list)
    for (ctype, model_id), model_obj in model_objs_map.items():
        model_objs_by_ctype[ctype].append(model_obj)

    # Build a dict of all entities that need to be synced. These include the original models
    # and any super entities from super_entities_by_ctype. This dict is keyed on ctype with
    # a list of IDs of each model
    model_ids_to_sync = defaultdict(set)
    for (ctype, model_id), model_obj in model_objs_map.items():
        model_ids_to_sync[ctype].add(model_obj.id)

    # For each ctype, obtain super entities. This is a dict keyed on ctype. Each value
    # is a dict keyed on the ctype of the super entity with a list of tuples for
    # IDs of sub/super entity relationships
    super_entities_by_ctype = _get_super_entities_by_ctype(model_objs_by_ctype, model_ids_to_sync, sync_all)

    # Now that we have all models we need to sync, fetch them so that we can extract
    # metadata and entity kinds. If we are syncing all entities, we've already fetched
    # everything and can fill in this data struct without doing another DB hit
    model_objs_to_sync = _get_model_objs_to_sync(model_ids_to_sync, model_objs_map, sync_all)

    # Obtain all entity kind tuples associated with the models
    entity_kind_tuples_to_sync = set()
    for ctype, model_objs_to_sync_for_ctype in model_objs_to_sync.items():
        entity_config = entity_registry.entity_registry.get(ctype.model_class())
        for model_obj in model_objs_to_sync_for_ctype:
            entity_kind_tuples_to_sync.add(entity_config.get_entity_kind(model_obj))

    # Upsert all entity kinds and obtain the map of them
    entity_kinds_to_upsert = [
        EntityKind(name=name, display_name=display_name)
        for name, display_name in entity_kind_tuples_to_sync
    ]
    with SyncLock(EntityKind, 'sync_entities__entity_kind'):
        upserted_entity_kinds = manager_utils.bulk_upsert2(
            EntityKind.all_objects.all(),
            entity_kinds_to_upsert,
            ['name'],
            ['display_name'],
            returning=['id', 'name'],
            ignore_duplicate_updates=True,
            return_untouched=True
        )
    entity_kinds_map = {
        entity_kind.name: entity_kind
        for entity_kind in upserted_entity_kinds
    }

    # Now that we have all entity kinds, build all entities that need to be synced
    entities_to_upsert = []
    for ctype, model_objs_to_sync_for_ctype in model_objs_to_sync.items():
        entity_config = entity_registry.entity_registry.get(ctype.model_class())
        entities_to_upsert.extend([
            Entity(
                entity_id=model_obj.id,
                entity_type_id=ctype.id,
                entity_kind_id=entity_kinds_map[entity_config.get_entity_kind(model_obj)[0]].id,
                entity_meta=entity_config.get_entity_meta(model_obj),
                display_name=entity_config.get_display_name(model_obj),
                is_active=entity_config.get_is_active(model_obj)
            )
            for model_obj in model_objs_to_sync_for_ctype
        ])

    # Upsert entities (or do a sync if we are updating all entities)
    with SyncLock(Entity, 'sync_entities__entity'):
        if model_objs:
            upserted_entities = manager_utils.bulk_upsert2(
                Entity.all_objects.all(),
                entities_to_upsert,
                ['entity_type_id', 'entity_id'],
                ['entity_kind_id', 'entity_meta', 'display_name', 'is_active'],
                returning=['id', 'entity_type_id', 'entity_id'],
                ignore_duplicate_updates=True,
                return_untouched=True
            )
        else:
            upserted_entities = manager_utils.sync2(
                Entity.all_objects.all(),
                entities_to_upsert,
                ['entity_type_id', 'entity_id'],
                ['entity_kind_id', 'entity_meta', 'display_name', 'is_active'],
                returning=['id', 'entity_type_id', 'entity_id'],
                ignore_duplicate_updates=True
            )

    entities_map = {
        (entity.entity_type_id, entity.entity_id): entity
        for entity in chain(
            upserted_entities.updated, upserted_entities.created, upserted_entities.untouched
        )
    }

    # Now that all entities are upserted, sync entity relationships
    entity_relationships_to_sync = [
        EntityRelationship(
            sub_entity_id=entities_map[sub_ctype.id, sub_entity_id].id,
            super_entity_id=entities_map[super_ctype.id, super_entity_id].id,
        )
        for sub_ctype, super_entities_by_sub_ctype in super_entities_by_ctype.items()
        for super_ctype, relationships in super_entities_by_sub_ctype.items()
        for sub_entity_id, super_entity_id in relationships
    ]
    # Find the entities of the original model objects we were syncing. These
    # are needed to properly sync entity relationships
    original_entity_ids = [
        entities_map[ctype.id, model_obj.id].id
        for ctype, model_objs_for_ctype in model_objs_by_ctype.items()
        for model_obj in model_objs_for_ctype
    ]

    if not model_objs:
        # If we're syncing everything, just sync against the entire entity relationship
        # table instead of doing a complex __in query
        sync_against = EntityRelationship.objects.all()
    else:
        sync_against = EntityRelationship.objects.filter(sub_entity_id__in=original_entity_ids)

    # Sync the relations
    with SyncLock(EntityRelationship, 'sync_entities__entity_relationship'):
        manager_utils.sync2(
            sync_against,
            entity_relationships_to_sync,
            ['sub_entity_id', 'super_entity_id'],
            [],
            ignore_duplicate_updates=True
        )


# Add a defer and buffer method to the sync entities method
# This is used by the defer_entity_syncing decorator
sync_entities.defer = False
sync_entities.buffer = {}


def sync_entities_watching(instance):
    """
    Syncs entities watching changes of a model instance.
    """
    for entity_model, entity_model_getter in entity_registry.entity_watching[instance.__class__]:
        model_objs = list(entity_model_getter(instance))
        if model_objs:
            sync_entities(*model_objs)
