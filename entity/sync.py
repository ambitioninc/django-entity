"""
Provides functions for syncing entities and their relationships to the
Entity and EntityRelationship tables.
"""
from itertools import chain

from django.contrib.contenttypes.models import ContentType
import manager_utils

from entity import entity_registry
from entity.models import Entity, EntityRelationship


class EntitySyncer(object):
    """
    Responsible for syncing entities. This object maintains a cache of synced entities so that syncing many entities
    that share super entities is faster.
    """
    def __init__(self):
        # A cache of all entities synced, keyed on the content type and model object id. Each key points to an Entity
        # model object
        self._synced_entity_cache = {}

        # A cache of all entity relationships that will need to be synced after all entities have been synced. This
        # dictionary is keyed on the subentity and has a list of super entities
        self._entity_relationships_to_sync = {}

    def _sync_entity(self, model_obj):
        entity_qset, entity_config = entity_registry.entity_registry.get(model_obj.__class__)
        entity_type = ContentType.objects.get_for_model(model_obj)

        if not self._synced_entity_cache.get((entity_type, model_obj.id)):
            # Create or update the entity
            entity = Entity.objects.upsert(
                entity_type=entity_type, entity_id=model_obj.id, updates={
                    'entity_meta': entity_config.get_entity_meta(model_obj),
                    'is_active': entity_config.is_entity_active(model_obj),
                })[0]

            # Cache all of the relationships that need to be synced
            self._entity_relationships_to_sync[entity] = [
                EntityRelationship(
                    super_entity=self._sync_entity(super_model_obj),
                    sub_entity=entity,
                )
                for super_model_obj in entity_config.get_super_entities(model_obj)
            ]

            # Cache the synced entity for later use
            self._synced_entity_cache[(entity_type, model_obj.id)] = entity

        return self._synced_entity_cache[(entity_type, model_obj.id)]

    def _sync_entity_relationships(self):
        """
        After all entities have been synced, the entity relationships of every synced entity is still
        stored in the _entity_relationships_to_sync variable. Sync these relationships.
        """
        manager_utils.sync(
            EntityRelationship.objects.filter(sub_entity__in=self._entity_relationships_to_sync.keys()),
            chain(*self._entity_relationships_to_sync.values()),
            ['super_entity_id', 'sub_entity_id']
        )

    def _sync_all_entities(self):
        """
        Syncs all entities across the project.
        """
        # Loop through all entities that inherit EntityModelMixin and sync the entity.
        for entity_model, (entity_qset, entity_config) in entity_registry.entity_registry.iteritems():
            model_objs = list(entity_qset.all())
            for model_obj in model_objs:
                self._sync_entity(model_obj)

            # Delete any existing entities that are not in the model obj table
            Entity.objects.filter(entity_type=ContentType.objects.get_for_model(entity_model)).exclude(
                entity_id__in=(model_obj.id for model_obj in model_objs)).delete()

    def sync_entities(self, *model_objs):
        """
        Sync entities of the provided model objects. If no model objects are provided, sync all entities in
        the project.
        """
        if model_objs:
            for model_obj in model_objs:
                self._sync_entity(model_obj)
        else:
            self._sync_all_entities()

        # After entities have been synced, their relationships have been cached in memory. Sync this to disk
        self._sync_entity_relationships()


def sync_entities(*model_objs):
    """
    Sync the provided model objects. If there are no model objects, sync all models across the entire
    project.
    """
    EntitySyncer().sync_entities(*model_objs)
