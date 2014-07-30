"""
Provides functions for syncing entities and their relationships to the
Entity and EntityRelationship tables.
"""
from collections import defaultdict
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

    def _sync_entity(self, model_obj, deep=True):
        """
        Syncs a single entity represented by model_obj. Appends its super entity relationship to the synced entity
        relationship cache if necessary.

        Note that this function operates in two modes - Shallow and deep. If deep is True, this function syncs
        relationships and syncs super entities in those relationships. If deep is False, the function only syncs
        relationships if the entity did not previously exist.
        """
        entity_config = entity_registry.entity_registry.get(model_obj.__class__)[1]
        entity_type = ContentType.objects.get_for_model(model_obj)

        if not self._synced_entity_cache.get((entity_type, model_obj.id, deep)):
            # Create or update the entity
            entity, created = Entity.objects.upsert(
                entity_type=entity_type, entity_id=model_obj.id, updates={
                    'entity_meta': entity_config.get_entity_meta(model_obj),
                    'is_active': entity_config.is_entity_active(model_obj),
                })

            # Cache all of the relationships that need to be synced. Do this only if in deep mode or if the entity
            # was created
            if created or deep:
                self._entity_relationships_to_sync[entity] = [
                    EntityRelationship(sub_entity=entity, super_entity=self._sync_entity(super_model_obj, deep=False))
                    for super_model_obj in entity_config.get_super_entities(model_obj)
                ]

            # Cache the synced entity for later use
            self._synced_entity_cache[(entity_type, model_obj.id, deep)] = entity

        return self._synced_entity_cache[(entity_type, model_obj.id, deep)]

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
            model_objs = list(entity_qset.all() if entity_qset is not None else entity_model.objects.all())
            for model_obj in model_objs:
                self._sync_entity(model_obj)

            # Delete any existing entities that are not in the model obj table
            Entity.objects.filter(entity_type=ContentType.objects.get_for_model(entity_model)).exclude(
                entity_id__in=(model_obj.id for model_obj in model_objs)).delete()

    def _sync_select_entities(self, *model_objs):
        """
        Syncs a selection of entities given as an array.
        """
        # Key each model obj on the model type and make a list of all obj ids for that type
        model_objs_per_type = defaultdict(list)
        for model_obj in model_objs:
            model_objs_per_type[model_obj.__class__].append(model_obj)

        # Sync entities of each type
        for model_type, model_objs in model_objs_per_type.iteritems():
            qset = entity_registry.entity_registry.get(model_type)[0]

            # Refetch the model objects if the user registered a queryset. This performs select/prefetch
            # relates on the queryset and speeds up individual entity syncing. Note - compare the querysets
            # instance to None rather than explicitly checking for equality. This prevents the queryset
            # from being evaluated if there is one
            if qset is not None:
                if len(model_objs) == 1:
                    model_objs = [qset.get(id=model_objs[0].id)]
                else:
                    model_objs = qset.filter(id__in=(model_obj.id for model_obj in model_objs))

            # Although we already have the model objecs to sync, fetch them again using their querysets. This
            # allows us to use less DB calls for entities that have many relationships
            for model_obj in model_objs:
                self._sync_entity(model_obj)

    def sync_entities_and_relationships(self, *model_objs):
        """
        Sync entities of the provided model objects. If no model objects are provided, sync all entities in
        the project.
        """
        if model_objs:
            self._sync_select_entities(*model_objs)
        else:
            self._sync_all_entities()

        # After entities have been synced, their relationships have been cached in memory. Sync this to disk
        self._sync_entity_relationships()
