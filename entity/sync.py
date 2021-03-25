"""
Provides functions for syncing entities and their relationships to the
Entity and EntityRelationship tables.
"""
import logging
from time import sleep

import wrapt
from collections import defaultdict

from activatable_model import model_activations_changed
from django import db
from django.contrib.contenttypes.models import ContentType
import manager_utils
from django.db import transaction, connection

from entity.config import entity_registry
from entity.models import Entity, EntityRelationship, EntityKind


LOG = logging.getLogger(__name__)


def transaction_atomic_with_retry(num_retries=5, backoff=0.1):
    """
    This is a decorator that will wrap the decorated method in an atomic transaction and
    retry the transaction a given number of times

    :param num_retries: How many times should we retry before we give up
    :param backoff: How long should we wait after each try
    """

    # Create the decorator
    @wrapt.decorator
    def wrapper(wrapped, instance, args, kwargs):
        # Keep track of how many times we have tried
        num_tries = 0
        exception = None

        # Call the main sync entities method and catch any exceptions
        while num_tries <= num_retries:
            # Try running the transaction
            try:
                with transaction.atomic():
                    return wrapped(*args, **kwargs)
            # Catch any operation errors
            except db.utils.OperationalError as e:
                num_tries += 1
                exception = e
                sleep(backoff * num_tries)

        # If we have an exception raise it
        raise exception

    # Return the decorator
    return wrapper


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
        if None in sync_entities.buffer:
            model_objs = list()

        # Sync the entities that were deferred if any
        if len(sync_entities.buffer):
            sync_entities(*model_objs)

        # Clear the buffer
        sync_entities.buffer = {}


@wrapt.decorator
def suppress_entity_syncing(wrapped, instance, args, kwargs):
    """
    A decorator that can be used to completely suppress syncing of entities as a result of
    execution of the decorated method
    """

    # Suppress entity syncing for the scope of the decorated method
    sync_entities.suppress = True

    # Run the method
    try:
        return wrapped(*args, **kwargs)

    # After we run the method return the entity sync state for future use
    finally:
        sync_entities.suppress = False


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


def _fetch_entity_models(model_ids_to_sync, model_objs_map, model_objs_by_ctype, sync_all):
    """
    Fetch the entity models per content type. This will also handle the
    case where accounts are created before _get_super_entities_by_ctype and
    the model_ids_to_sync do not match the model_objs_map
    """
    for ctype, model_ids in model_ids_to_sync.items():

        if sync_all:

            # Build a set of ids of already fetched models
            fetched_model_ids = {
                model.id
                for model in model_objs_by_ctype[ctype]
            }

            # Compute the set diff to see if any records are missing
            unfetched_model_ids = model_ids - fetched_model_ids
        else:
            unfetched_model_ids = model_ids

        # Check if new records
        if unfetched_model_ids:

            # Fetch the records and add them to the model_objs_map
            model_qset = entity_registry.entity_registry.get(ctype.model_class()).queryset
            model_objs_to_sync = model_qset.filter(id__in=unfetched_model_ids)
            for model_obj in model_objs_to_sync:
                model_objs_by_ctype[ctype].append(model_obj)
                model_objs_map[(ctype, model_obj.id)] = model_obj


def _get_model_objs_to_sync(model_ids_to_sync, model_objs_map, model_objs_by_ctype, sync_all):
    """
    Given the model IDs to sync, fetch all model objects to sync
    """
    model_objs_to_sync = {}

    _fetch_entity_models(model_ids_to_sync, model_objs_map, model_objs_by_ctype, sync_all)

    for ctype, model_ids_to_sync_for_ctype in model_ids_to_sync.items():
        model_objs_to_sync[ctype] = [
            model_objs_map[ctype, model_id]
            for model_id in model_ids_to_sync_for_ctype
        ]

    return model_objs_to_sync


def sync_entities(*model_objs):
    """
    Syncs entities

    Args:
        model_objs (List[Model]): The model objects to sync. If empty, all entities will be synced
    """
    if sync_entities.suppress:
        # Return false that we did not do anything
        return False

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

    # Create a syncer and sync
    EntitySyncer(*model_objs).sync()


# Add a defer and buffer method to the sync entities method
# This is used by the defer_entity_syncing decorator
sync_entities.defer = False
sync_entities.buffer = {}
# Add a suppress attribute to the sync entities method
sync_entities.suppress = False


def sync_entities_watching(instance):
    """
    Syncs entities watching changes of a model instance.
    """
    for entity_model, entity_model_getter in entity_registry.entity_watching[instance.__class__]:
        model_objs = list(entity_model_getter(instance))
        if model_objs:
            sync_entities(*model_objs)


class EntitySyncer(object):
    """
    A class that will handle the syncing of entities
    """

    def __init__(self, *model_objs):
        """
        Initialize the entity syncer with the models we need to sync
        """

        # Set the model objects
        self.model_objs = model_objs

        # Are we syncing all
        self.sync_all = not model_objs

    def sync(self):
        # Log what we are syncing
        LOG.debug('sync_entities')
        LOG.debug(self.model_objs)

        # Determine if we are syncing all
        sync_all = not self.model_objs
        model_objs_map = {
            (ContentType.objects.get_for_model(model_obj, for_concrete_model=False), model_obj.id): model_obj
            for model_obj in self.model_objs
        }

        # If we are syncing all build the entire map for all entity types
        if self.sync_all:
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
        model_objs_to_sync = _get_model_objs_to_sync(model_ids_to_sync, model_objs_map, model_objs_by_ctype, sync_all)

        # Obtain all entity kind tuples associated with the models
        entity_kind_tuples_to_sync = set()
        for ctype, model_objs_to_sync_for_ctype in model_objs_to_sync.items():
            entity_config = entity_registry.entity_registry.get(ctype.model_class())
            for model_obj in model_objs_to_sync_for_ctype:
                entity_kind_tuples_to_sync.add(entity_config.get_entity_kind(model_obj))

        # Build the entity kinds that we need to sync
        entity_kinds_to_upsert = [
            EntityKind(name=name, display_name=display_name)
            for name, display_name in entity_kind_tuples_to_sync
        ]

        # Upsert the entity kinds
        upserted_entity_kinds = self.upsert_entity_kinds(
            entity_kinds=entity_kinds_to_upsert
        )

        # Build a map of entity kind name to entity kind
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

        # Upsert the entities and get the upserted entities and the changed state
        upserted_entities, changed_entity_activation_state = self.upsert_entities(
            entities=entities_to_upsert,
            sync=self.sync_all
        )

        # Call the model activations changed signal manually since we have done a bulk operation
        self.send_entity_activation_events(changed_entity_activation_state)

        # Create a map out of entities
        entities_map = {
            (entity.entity_type_id, entity.entity_id): entity
            for entity in upserted_entities
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
            if (sub_ctype.id, sub_entity_id) in entities_map and (super_ctype.id, super_entity_id) in entities_map
        ]

        # Find the entities of the original model objects we were syncing. These
        # are needed to properly sync entity relationships
        original_entity_ids = [
            entities_map[ctype.id, model_obj.id].id
            for ctype, model_objs_for_ctype in model_objs_by_ctype.items()
            for model_obj in model_objs_for_ctype
            if (ctype.id, model_obj.id) in entities_map
        ]

        if self.sync_all:
            # If we're syncing everything, just sync against the entire entity relationship
            # table instead of doing a complex __in query
            sync_against = EntityRelationship.objects.all()
        else:
            sync_against = EntityRelationship.objects.filter(sub_entity_id__in=original_entity_ids)

        # Sync the relations
        self.upsert_entity_relationships(
            queryset=sync_against,
            entity_relationships=entity_relationships_to_sync
        )

    @transaction_atomic_with_retry()
    def upsert_entity_kinds(self, entity_kinds):
        """
        Given a list of entity kinds ensure they are synced properly to the database.
        This will ensure that only unchanged entity kinds are synced and will still return all
        updated entity kinds

        :param entity_kinds: The list of entity kinds to sync
        """

        # Filter out unchanged entity kinds
        unchanged_entity_kinds = {}
        if entity_kinds:
            unchanged_entity_kinds = {
                (entity_kind.name, entity_kind.display_name): entity_kind
                for entity_kind in EntityKind.all_objects.extra(
                    where=['(name, display_name) IN %s'],
                    params=[tuple(
                        (entity_kind.name, entity_kind.display_name)
                        for entity_kind in entity_kinds
                    )]
                )
            }

        # Filter out the unchanged entity kinds
        changed_entity_kinds = [
            entity_kind
            for entity_kind in entity_kinds
            if (entity_kind.name, entity_kind.display_name) not in unchanged_entity_kinds
        ]

        # If any of our kinds have changed upsert them
        upserted_enitity_kinds = []
        if changed_entity_kinds:
            # Select all our existing entity kinds for update so we can do proper locking
            # We have to select all here for some odd reason, if we only select the ones
            # we are syncing we still run into deadlock issues
            list(EntityKind.all_objects.all().order_by('id').select_for_update().values_list('id', flat=True))

            # Upsert the entity kinds
            upserted_enitity_kinds = manager_utils.bulk_upsert(
                queryset=EntityKind.all_objects.filter(
                    name__in=[entity_kind.name for entity_kind in changed_entity_kinds]
                ),
                model_objs=changed_entity_kinds,
                unique_fields=['name'],
                update_fields=['display_name'],
                return_upserts=True
            )

        # Return all the entity kinds
        return upserted_enitity_kinds + list(unchanged_entity_kinds.values())

    @transaction_atomic_with_retry()
    def upsert_entities(self, entities, sync=False):
        """
        Upsert a list of entities to the database
        :param entities: The entities to sync
        :param sync: Do a sync instead of an upsert
        """

        # Select the entities we are upserting for update to reduce deadlocks
        if entities:
            # Default select for update query when syncing all
            select_for_update_query = (
                'SELECT FROM {table_name} ORDER BY id ASC FOR NO KEY UPDATE'
            ).format(
                table_name=Entity._meta.db_table
            )
            select_for_update_query_params = []

            # If we are not syncing all, only select those we are updating
            if not sync:
                select_for_update_query = (
                    'SELECT FROM {table_name} '
                    'WHERE (entity_type_id, entity_id) IN %s '
                    'ORDER BY id ASC '
                    'FOR NO KEY UPDATE'
                ).format(
                    table_name=Entity._meta.db_table
                )
                select_for_update_query_params = [tuple(
                    (entity.entity_type_id, entity.entity_id)
                    for entity in entities
                )]

            # Select the items for update
            with connection.cursor() as cursor:
                cursor.execute(select_for_update_query, select_for_update_query_params)

        # Compute the initial queryset and the initial state of the entities we are syncing
        # We need the initial state so we can compare it to the new state to determine any
        # entities that were activated or deactivated
        initial_queryset = Entity.all_objects.all()
        if not sync:
            initial_queryset = Entity.all_objects.extra(
                where=['(entity_type_id, entity_id) IN %s'],
                params=[tuple(
                    (entity.entity_type_id, entity.entity_id)
                    for entity in entities
                )]
            )
        initial_entity_activation_state = {
            entity[0]: entity[1]
            for entity in initial_queryset.values_list('id', 'is_active')
        }

        # Sync all the entities if the sync flag is passed
        if sync:
            upserted_entities = manager_utils.sync(
                queryset=initial_queryset,
                model_objs=entities,
                unique_fields=['entity_type_id', 'entity_id'],
                update_fields=['entity_kind_id', 'entity_meta', 'display_name', 'is_active'],
                return_upserts=True
            )
        # Otherwise we want to upsert our entities
        else:
            upserted_entities = manager_utils.bulk_upsert(
                queryset=initial_queryset,
                model_objs=entities,
                unique_fields=['entity_type_id', 'entity_id'],
                update_fields=['entity_kind_id', 'entity_meta', 'display_name', 'is_active'],
                return_upserts=True
            )

        # Compute the current state of the entities
        current_entity_activation_state = {
            entity.id: entity.is_active
            for entity in upserted_entities
        }

        # Computed the changed activation state of the entities
        changed_entity_activation_state = {}
        all_entity_ids = set(initial_entity_activation_state.keys()) | set(current_entity_activation_state.keys())
        for entity_id in all_entity_ids:
            # Get the initial activation state of the entity
            # Default to false so we only detect when the model has actually changed
            initial_activation_state = initial_entity_activation_state.get(entity_id, False)

            # Get the current state of the entity
            # Default to false here since the upserts do not return is_active=False due
            # to the default object manager excluding these
            current_activation_state = current_entity_activation_state.get(entity_id, False)

            # Check if the state changed and at it to the changed entity state
            if initial_activation_state != current_activation_state:
                changed_entity_activation_state[entity_id] = current_activation_state

        # Return the upserted entities
        return upserted_entities, changed_entity_activation_state

    @transaction_atomic_with_retry()
    def upsert_entity_relationships(self, queryset, entity_relationships):
        """
        Upsert entity relationships to the database
        :param queryset: The base queryset to use
        :param entity_relationships: The entity relationships to ensure exist in the database
        """

        # Select the relationships for update
        if entity_relationships:
            list(queryset.order_by('id').select_for_update().values_list(
                'id',
                flat=True
            ))

        # Sync the relationships
        return manager_utils.sync(
            queryset=queryset,
            model_objs=entity_relationships,
            unique_fields=['sub_entity_id', 'super_entity_id'],
            update_fields=[],
            return_upserts=True
        )

    def send_entity_activation_events(self, changed_entity_activation_state):
        """
        Given a changed entity state dict, fire the appropriate signals
        :param changed_entity_activation_state: The changed entity activation state {entity_id: is_active}
        """

        # Compute the activated and deactivated entities
        activated_entities = set()
        deactivated_entities = set()
        for entity_id, is_active in changed_entity_activation_state.items():
            if is_active:
                activated_entities.add(entity_id)
            else:
                deactivated_entities.add(entity_id)

        # If any entities were activated call the activation change event with the active flag
        if activated_entities:
            model_activations_changed.send(
                sender=Entity,
                instance_ids=sorted(list(activated_entities)),
                is_active=True
            )

        # If any entities were deactivated call the activation change event with the active flag as false
        if deactivated_entities:
            model_activations_changed.send(
                sender=Entity,
                instance_ids=sorted(list(deactivated_entities)),
                is_active=False
            )
