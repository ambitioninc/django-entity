"""
Provides functions for syncing entities and their relationships to the
Entity and EntityRelationship tables.
"""
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_save, post_delete
from manager_utils import sync

from .models import Entity, EntityRelationship, EntityModelMixin, delete_entity_signal_handler
from .models import save_entity_signal_handler, bulk_operation_signal_handler, post_bulk_operation


def turn_off_syncing():
    """
    Disables all of the signals for syncing entities.
    """
    post_delete.disconnect(delete_entity_signal_handler, dispatch_uid='delete_entity_signal_handler')
    post_save.disconnect(save_entity_signal_handler, dispatch_uid='save_entity_signal_handler')
    post_bulk_operation.disconnect(bulk_operation_signal_handler, dispatch_uid='bulk_operation_signal_handler')


def turn_on_syncing():
    """
    Enables all of the signals for syncing entities.
    """
    post_delete.connect(delete_entity_signal_handler, dispatch_uid='delete_entity_signal_handler')
    post_save.connect(save_entity_signal_handler, dispatch_uid='save_entity_signal_handler')
    post_bulk_operation.connect(bulk_operation_signal_handler, dispatch_uid='bulk_operation_signal_handler')


def sync_entity(model_obj, is_deleted, entity_cache=None):
    """
    Given a model object, either delete it from the entity table (if
    is_deleted=False) or update its entity values and relationships.
    """
    entity_type = ContentType.objects.get_for_model(model_obj)

    if is_deleted:
        # Delete the entity, taking in the case of where the entity may not exist
        # before hand
        Entity.objects.filter(entity_type=entity_type, entity_id=model_obj.id).delete()
    else:
        entity_cache = entity_cache if entity_cache is not None else {}

        if not entity_cache.get((entity_type, model_obj.id)):
            # Create or update the entity
            entity = Entity.objects.upsert(
                entity_type=entity_type, entity_id=model_obj.id, updates={
                    'entity_meta': model_obj.get_entity_meta(),
                    'is_active': model_obj.is_entity_active(),
                })[0]

            # Delete all of the existing relationships super to this entity
            sync(entity.super_relationships.all(), [
                EntityRelationship(
                    super_entity=sync_entity(super_model_obj, False, entity_cache),
                    sub_entity=entity,
                )
                for super_model_obj in model_obj.get_super_entities()
            ], ['super_entity_id', 'sub_entity_id'])

            entity_cache[(entity_type, model_obj.id)] = entity

        return entity_cache[(entity_type, model_obj.id)]


def sync_entities():
    """
    Sync all entities in a project.
    """
    # Instantiate a cache that will be used by all calls to sync_entity
    entity_cache = {}

    # Loop through all entities that inherit EntityModelMixin and sync the entity.
    entity_models = [model_class for model_class in models.get_models() if issubclass(model_class, EntityModelMixin)]
    for entity_model in entity_models:
        model_objs = list(entity_model.objects.all())
        for model_obj in model_objs:
            sync_entity(model_obj, False, entity_cache)

        # Delete any existing entities that are not in the model obj table
        Entity.objects.filter(entity_type=ContentType.objects.get_for_model(entity_model)).exclude(
            entity_id__in=(model_obj.id for model_obj in model_objs)).delete()
