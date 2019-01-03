"""
Provides functions for syncing entities and their relationships to the
Entity and EntityRelationship tables.
"""
from collections import defaultdict
from itertools import chain

from django.contrib.contenttypes.models import ContentType
import manager_utils

from entity.config import entity_registry
from entity.models import Entity, EntityRelationship, EntityKind


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
    created_entity_kinds, updated_entity_kinds = manager_utils.bulk_upsert2(
        EntityKind.all_objects.all(),
        entity_kinds_to_upsert,
        ['name'],
        ['display_name'],
        returning=True)
    entity_kinds_map = {
        entity_kind.name: entity_kind
        for entity_kind in chain(created_entity_kinds, updated_entity_kinds)
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
    if model_objs:
        created_entities, updated_entities = manager_utils.bulk_upsert2(
            Entity.all_objects.all(),
            entities_to_upsert,
            ['entity_type_id', 'entity_id'],
            ['entity_kind_id', 'entity_meta', 'display_name', 'is_active'],
            returning=True)
    else:
        created_entities, updated_entities, _ = manager_utils.sync2(
            Entity.all_objects.all(),
            entities_to_upsert,
            ['entity_type_id', 'entity_id'],
            ['entity_kind_id', 'entity_meta', 'display_name', 'is_active'],
            returning=True)

    entities_map = {
        (entity.entity_type_id, entity.entity_id): entity
        for entity in chain(created_entities, updated_entities)
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
        entities_map[ctype.id, model_obj.id]
        for ctype, model_objs_for_ctype in model_objs_by_ctype.items()
        for model_obj in model_objs_for_ctype
    ]

    if not model_objs:
        # If we're syncing everything, just sync against the entire entity relationship
        # table instead of doing a complex __in query
        sync_against = EntityRelationship.objects.all()
    else:
        sync_against = EntityRelationship.objects.filter(sub_entity__in=original_entity_ids)

    manager_utils.sync2(
        sync_against,
        entity_relationships_to_sync,
        ['sub_entity_id', 'super_entity_id']
    )


def sync_entities_watching(instance):
    """
    Syncs entities watching changes of a model instance.
    """
    for entity_model, entity_model_getter in entity_registry.entity_watching[instance.__class__]:
        model_objs = list(entity_model_getter(instance))
        if model_objs:
            sync_entities(*model_objs)
