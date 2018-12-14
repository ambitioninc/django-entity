"""
Provides functions for syncing entities and their relationships to the
Entity and EntityRelationship tables.
"""
from collections import defaultdict
from itertools import chain

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
import manager_utils

from entity.config import entity_registry
import entity.db as entity_db
from entity.models import Entity, EntityRelationship, EntityKind


def sync(*model_objs):
    # Organize by content type
    model_objs_by_ctype = defaultdict(list)
    for model_obj in model_objs:
        ctype = ContentType.objects.get_for_model(model_obj, for_concrete_model=False)
        model_objs_by_ctype[ctype].append(model_obj)

    # Build a dict of all entities that need to be synced. These include the original models
    # and any super entities from super_entities_by_ctype. This dict is keyed on ctype with
    # a list of IDs of each model
    model_ids_to_sync = defaultdict(set)
    for model_obj in model_objs:
        ctype = ContentType.objects.get_for_model(model_obj, for_concrete_model=False)
        model_ids_to_sync[ctype].add(model_obj.id)

    # For each ctype, obtain super entities. This is a dict keyed on ctype. Each value
    # is a dict keyed on the ctype of the super entity with a list of tuples for
    # IDs of sub/super entity relationships
    super_entities_by_ctype = defaultdict(lambda: defaultdict(list))
    for ctype, model_objs_for_ctype in model_objs_by_ctype.items():
        entity_config = entity_registry.entity_registry.get(ctype.model_class())[1]
        super_entities_by_ctype[ctype] = {
            ContentType.objects.get_for_model(model_class, for_concrete_model=False): relationships
            for model_class, relationships in entity_config.bulk_get_super_entities(model_objs_for_ctype).items()
        }

        # Continue adding to the set of entities that need to be synced
        for super_entity_ctype, relationships in super_entities_by_ctype[ctype].items():
            for sub_entity_id, super_entity_id in relationships:
                model_ids_to_sync[ctype].add(sub_entity_id)
                model_ids_to_sync[super_entity_ctype].add(super_entity_id)

    # Now that we have all models we need to sync, fetch them so that we can extract
    # metadata and entity kinds.
    model_objs_to_sync = {}
    for ctype, model_ids_to_sync_for_ctype in model_ids_to_sync.items():

        model_qset = entity_registry.entity_registry.get(ctype.model_class())[0] or ctype.model_class().objects
        model_objs_to_sync[ctype] = model_qset.filter(id__in=model_ids_to_sync_for_ctype)

    # Obtain all entity kind tuples associated with the models
    entity_kind_tuples_to_sync = set()
    for ctype, model_objs_to_sync_for_ctype in model_objs_to_sync.items():
        entity_config = entity_registry.entity_registry.get(ctype.model_class())[1]
        for model_obj in model_objs_to_sync_for_ctype:
            entity_kind_tuples_to_sync.add(entity_config.get_entity_kind(model_obj))

    # Upsert all entity kinds and obtain the map of them
    entity_kinds_to_upsert = [
        EntityKind(name=name, display_name=display_name)
        for name, display_name in entity_kind_tuples_to_sync
    ]
    created_entity_kinds, updated_entity_kinds, _ = entity_db.upsert(
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
        entity_config = entity_registry.entity_registry.get(ctype.model_class())[1]
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
    created_entities, updated_entities, _ = entity_db.upsert(
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
        for ctype, model_objs in model_objs_by_ctype.items()
        for model_obj in model_objs
    ]
    entity_db.upsert(
        EntityRelationship.objects.filter(sub_entity__in=original_entity_ids),
        entity_relationships_to_sync,
        ['sub_entity_id', 'super_entity_id'],
        sync=True
    )


class EntitySyncer(object):
    """
    Responsible for syncing entities.

    This object maintains a cache of synced entities so that syncing many entities that share super entities is faster.
    """
    def __init__(self):
        # A cache of all entities synced, keyed on the content type and model object id. Each key points to an Entity
        # model object
        self._synced_entity_cache = {}

        # A cached of synced entity kinds, keyed on the entity kind name
        self._synced_entity_kind_cache = {}

        # A cache of all entity relationships that will need to be synced after all entities have been synced. This
        # dictionary is keyed on the subentity and has a list of super entities
        self._entity_relationships_to_sync = {}

    def _get_entity_kind(self, entity_config, model_obj):
        """
        Obtains an entity kind for a model obj, caching the values (and retrieving values from cache) when necessary.

        :param entity_config: The entity config
        :type entity_config: entity.config.EntityConfig

        :param model_obj: The model
        :type model_obj: django.db.models.Model
        """

        # Get the entity kind name and display name
        entity_kind_name, entity_kind_display_name = entity_config.get_entity_kind(model_obj)

        # If this entity kind is not in the cache, create it and store in the cache
        if entity_kind_name not in self._synced_entity_kind_cache:
            self._synced_entity_kind_cache[entity_kind_name] = EntityKind.all_objects.upsert(
                name=entity_kind_name,
                updates={
                    'display_name': entity_kind_display_name
                }
            )[0]

        # Return the entity kind
        return self._synced_entity_kind_cache[entity_kind_name]

    def _sync_entity(self, model_obj, deep=True):
        """
        Syncs a single entity represented by model_obj. Appends its super entity relationship to the synced entity
        relationship cache if necessary.

        Note that this function operates in two modes - Shallow and deep. If deep is True, this function syncs
        relationships and syncs super entities in those relationships. If deep is False, the function only syncs
        relationships if the entity did not previously exist.
        """
        entity_config = entity_registry.entity_registry.get(model_obj.__class__)[1]
        entity_type = ContentType.objects.get_for_model(model_obj, for_concrete_model=False)

        if not self._synced_entity_cache.get((entity_type, model_obj.id, deep)):
            # Get the entity kind related to this entity
            entity_kind = self._get_entity_kind(entity_config, model_obj)

            # Create or update the entity
            entity, created = Entity.all_objects.upsert(
                entity_type=entity_type, entity_id=model_obj.id, updates={
                    'entity_meta': entity_config.get_entity_meta(model_obj),
                    'display_name': entity_config.get_display_name(model_obj),
                    'is_active': entity_config.get_is_active(model_obj),
                    'entity_kind_id': entity_kind.id,
                })

            # Cache all of the relationships that need to be synced. Do this only if in deep mode or if the entity
            # was created
            if created or deep:
                # Get the super relations by map so we avoid duplicates
                super_relations = {}
                for super_model_obj in entity_config.get_super_entities(model_obj):
                    super_entity = self._sync_entity(super_model_obj, deep=False)
                    super_relations[super_entity.id] = EntityRelationship(sub_entity=entity, super_entity=super_entity)
                self._entity_relationships_to_sync[entity] = super_relations.values()

            # Cache the synced entity for later use
            self._synced_entity_cache[(entity_type, model_obj.id, deep)] = entity

        return self._synced_entity_cache[(entity_type, model_obj.id, deep)]

    def _sync_entity_relationships(self):
        """
        After all entities have been synced, the entity relationships of every synced entity is still
        stored in the _entity_relationships_to_sync variable. Sync these relationships.
        """
        manager_utils.sync(
            queryset=EntityRelationship.objects.filter(
                sub_entity__in=self._entity_relationships_to_sync.keys()
            ),
            model_objs=chain(*self._entity_relationships_to_sync.values()),
            unique_fields=['super_entity_id', 'sub_entity_id']
        )

    def _sync_all_entities(self):
        """
        Syncs all entities across the project.
        """
        # Loop through all entities that inherit EntityModelMixin and sync the entity.
        for entity_model, (entity_qset, entity_config) in entity_registry.entity_registry.items():
            # Get the queryset to use
            entity_qset = entity_qset if entity_qset is not None else entity_model.objects

            # Iterate over all the entity items in this models queryset
            paginator = Paginator(entity_qset.order_by('pk').all(), 1000)
            for page in range(1, paginator.num_pages + 1):
                for model_obj in paginator.page(page).object_list:
                    # Sync the entity
                    self._sync_entity(model_obj)

            # Get the content type
            content_type = ContentType.objects.get_for_model(
                entity_model,
                for_concrete_model=False
            )

            # Delete any existing entities that no longer exist in the model object table
            Entity.all_objects.filter(
                entity_type=content_type
            ).exclude(
                entity_id__in=entity_qset.all().values_list('pk', flat=True)
            ).delete(
                force=True
            )

    def _sync_select_entities(self, *model_objs):
        """
        Syncs a selection of entities given as an array.
        """
        # Key each model obj on the model type and make a list of all obj ids for that type
        model_objs_per_type = defaultdict(list)
        for model_obj in model_objs:
            model_objs_per_type[model_obj.__class__].append(model_obj)

        # Sync entities of each type
        for model_type, model_objs in model_objs_per_type.items():
            qset, entity_config = entity_registry.entity_registry.get(model_type)

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


def sync_entities(*model_objs):
    """
    Sync the provided model objects.
    If there are no model objects, sync all models across the entire project.
    """
    if model_objs:
        sync(*model_objs)
    else:
        # Import entity syncer here to avoid circular import
        from entity.sync import EntitySyncer
        EntitySyncer().sync_entities_and_relationships(*model_objs)


def sync_entities_watching(instance):
    """
    Syncs entities watching changes of a model instance.
    """
    for entity_model, entity_model_getter in entity_registry.entity_watching[instance.__class__]:
        entity_model_qset, entity_config = entity_registry.entity_registry[entity_model]
        if entity_model_qset is None:
            entity_model_qset = entity_model.objects.all()

        model_objs = list(entity_model_getter(instance))
        if model_objs:
            sync_entities(*model_objs)
