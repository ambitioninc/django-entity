"""
Provides functions for syncing entities and their relationships to the
Entity and EntityRelationship tables.
"""
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, post_delete
import manager_utils

from entity import entity_registry
from entity.models import Entity, EntityRelationship, delete_entity_signal_handler
from entity.models import save_entity_signal_handler, bulk_operation_signal_handler


def turn_off_syncing():
    """
    Disables all of the signals for syncing entities. If bulk is True, disable syncing on bulk operations.
    """
    post_delete.disconnect(delete_entity_signal_handler, dispatch_uid='delete_entity_signal_handler')
    post_save.disconnect(save_entity_signal_handler, dispatch_uid='save_entity_signal_handler')
    manager_utils.post_bulk_operation.disconnect(
        bulk_operation_signal_handler, dispatch_uid='bulk_operation_signal_handler')


def turn_on_syncing(bulk=False):
    """
    Enables all of the signals for syncing entities. If bulk is True, enable syncing on bulk operations.
    """
    post_delete.connect(delete_entity_signal_handler, dispatch_uid='delete_entity_signal_handler')
    post_save.connect(save_entity_signal_handler, dispatch_uid='save_entity_signal_handler')
    if bulk:
        manager_utils.post_bulk_operation.connect(
            bulk_operation_signal_handler, dispatch_uid='bulk_operation_signal_handler')


class EntitySyncer(object):
    """
    Responsible for syncing entities. This object maintains a cache of synced entities so that syncing many entities
    that share super entities is faster.
    """
    def __init__(self):
        self._entity_cache = {}

    def sync_entity(self, model_obj, is_deleted=False):
        entity_qset, entity_config = entity_registry.entity_registry.get(model_obj.__class__)
        entity_type = ContentType.objects.get_for_model(model_obj)

        if is_deleted:
            # Delete the entity, taking in the case of where the entity may not exist
            # before hand
            Entity.objects.filter(entity_type=entity_type, entity_id=model_obj.id).delete()
        else:
            if not self._entity_cache.get((entity_type, model_obj.id)):
                # Create or update the entity
                entity = Entity.objects.upsert(
                    entity_type=entity_type, entity_id=model_obj.id, updates={
                        'entity_meta': entity_config.get_entity_meta(model_obj),
                        'is_active': entity_config.is_entity_active(model_obj),
                    })[0]

                # Delete all of the existing relationships super to this entity
                manager_utils.sync(entity.super_relationships.all(), [
                    EntityRelationship(
                        super_entity=self.sync_entity(super_model_obj, False),
                        sub_entity=entity,
                    )
                    for super_model_obj in entity_config.get_super_entities(model_obj)
                ], ['super_entity_id', 'sub_entity_id'])

                self._entity_cache[(entity_type, model_obj.id)] = entity

            return self._entity_cache[(entity_type, model_obj.id)]


def sync_entities():
    """
    Sync all entities in a project.
    """
    entity_syncer = EntitySyncer()

    # Loop through all entities that inherit EntityModelMixin and sync the entity.
    for entity_model, (entity_qset, entity_config) in entity_registry.entity_registry.iteritems():
        model_objs = list(entity_qset.all())
        for model_obj in model_objs:
            entity_syncer.sync_entity(model_obj)

        # Delete any existing entities that are not in the model obj table
        Entity.objects.filter(entity_type=ContentType.objects.get_for_model(entity_model)).exclude(
            entity_id__in=(model_obj.id for model_obj in model_objs)).delete()
