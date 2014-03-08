"""
Provides functions for syncing entities and their relationships to the
Entity and EntityRelationship tables.
"""
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_save, post_delete

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


def sync_entity(model_obj, is_deleted):
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
        # Create or update the entity
        entity_meta = model_obj.get_entity_meta()
        is_active = model_obj.is_entity_active()
        entity, is_created = Entity.objects.get_or_create(
            entity_type=entity_type, entity_id=model_obj.id, defaults={
                'entity_meta': entity_meta,
                'is_active': is_active,
            })
        if not is_created:
            # Update the entity attributes here if it wasn't created
            entity.entity_meta = entity_meta
            entity.is_active = is_active
            entity.save()

        # Delete all of the existing relationships super to this entity
        entity.super_relationships.all().delete()

        # For every super entity, create an entity relationship
        entity_relationships = []
        for super_model_obj in model_obj.get_super_entities():
            # Sync the super entity
            super_entity = sync_entity(super_model_obj, False)
            # Make a relationship with the super entity
            entity_relationships.append(EntityRelationship(
                super_entity=super_entity,
                sub_entity=entity,
            ))
        EntityRelationship.objects.bulk_create(entity_relationships)

        return entity


def sync_entities():
    """
    Sync all entities in a project.
    """
    # Loop through all entities that inherit EntityModelMixin and sync the entity.
    entity_models = [model_class for model_class in models.get_models() if issubclass(model_class, EntityModelMixin)]
    for entity_model in entity_models:
        model_obj_ids = []
        for model_obj in entity_model.objects.all():
            sync_entity(model_obj, False)
            model_obj_ids.append(model_obj.id)

        # Delete any existing entities that are not in the model obj table
        Entity.objects.filter(entity_type=ContentType.objects.get_for_model(entity_model)).exclude(
            entity_id__in=model_obj_ids).delete()
