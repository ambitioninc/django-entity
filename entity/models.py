from itertools import compress

from activatable_model.models import BaseActivatableModel, ActivatableManager, ActivatableQuerySet
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import JSONField
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Count, Q
from python3_utils import compare_on_attr
from six.moves import reduce


class AllEntityKindManager(ActivatableManager):
    """
    Provides additional filtering for entity kinds.
    """
    pass


class ActiveEntityKindManager(AllEntityKindManager):
    """
    Provides additional filtering for entity kinds.
    """
    def get_queryset(self):
        return super(ActiveEntityKindManager, self).get_queryset().filter(is_active=True)


class EntityKind(BaseActivatableModel):
    """
    A kind for an Entity that is useful for filtering based on different types of entities.
    """
    # The unique identification string for the entity kind
    name = models.CharField(max_length=256, unique=True, db_index=True)

    # A human-readable string for the entity kind
    display_name = models.TextField(blank=True)

    # True if the entity kind is active
    is_active = models.BooleanField(default=True)

    objects = ActiveEntityKindManager()
    all_objects = AllEntityKindManager()

    def __str__(self):
        return self.display_name


class EntityQuerySet(ActivatableQuerySet):
    """
    Provides additional queryset filtering abilities.
    """
    def active(self):
        """
        Returns active entities.
        """
        return self.filter(is_active=True)

    def inactive(self):
        """
        Returns inactive entities.
        """
        return self.filter(is_active=False)

    def is_any_kind(self, *entity_kinds):
        """
        Returns entities that have any of the kinds listed in entity_kinds.
        """
        return self.filter(entity_kind__in=entity_kinds) if entity_kinds else self

    def is_not_any_kind(self, *entity_kinds):
        """
        Returns entities that do not have any of the kinds listed in entity_kinds.
        """
        return self.exclude(entity_kind__in=entity_kinds) if entity_kinds else self

    def is_sub_to_all(self, *super_entities):
        """
        Given a list of super entities, return the entities that have those as a subset of their super entities.
        """
        if super_entities:
            if len(super_entities) == 1:
                # Optimize for the case of just one super entity since this is a much less intensive query
                has_subset = EntityRelationship.objects.filter(
                    super_entity=super_entities[0]).values_list('sub_entity', flat=True)
            else:
                # Get a list of entities that have super entities with all types
                has_subset = EntityRelationship.objects.filter(
                    super_entity__in=super_entities).values('sub_entity').annotate(Count('super_entity')).filter(
                    super_entity__count=len(set(super_entities))).values_list('sub_entity', flat=True)

            return self.filter(id__in=has_subset)
        else:
            return self

    def is_sub_to_any(self, *super_entities):
        """
        Given a list of super entities, return the entities that have super entities that interset with those provided.
        """
        if super_entities:
            return self.filter(id__in=EntityRelationship.objects.filter(
                super_entity__in=super_entities).values_list('sub_entity', flat=True))
        else:
            return self

    def is_sub_to_all_kinds(self, *super_entity_kinds):
        """
        Each returned entity will have superentites whos combined entity_kinds included *super_entity_kinds
        """
        if super_entity_kinds:
            if len(super_entity_kinds) == 1:
                # Optimize for the case of just one
                has_subset = EntityRelationship.objects.filter(
                    super_entity__entity_kind=super_entity_kinds[0]).values_list('sub_entity', flat=True)
            else:
                # Get a list of entities that have super entities with all types
                has_subset = EntityRelationship.objects.filter(
                    super_entity__entity_kind__in=super_entity_kinds).values('sub_entity').annotate(
                    Count('super_entity')).filter(super_entity__count=len(set(super_entity_kinds))).values_list(
                    'sub_entity', flat=True)

            return self.filter(pk__in=has_subset)
        else:
            return self

    def is_sub_to_any_kind(self, *super_entity_kinds):
        """
        Find all entities that have super_entities of any of the specified kinds
        """
        if super_entity_kinds:
            # get the pks of the desired subs from the relationships table
            if len(super_entity_kinds) == 1:
                entity_pks = EntityRelationship.objects.filter(
                    super_entity__entity_kind=super_entity_kinds[0]
                ).select_related('entity_kind', 'sub_entity').values_list('sub_entity', flat=True)
            else:
                entity_pks = EntityRelationship.objects.filter(
                    super_entity__entity_kind__in=super_entity_kinds
                ).select_related('entity_kind', 'sub_entity').values_list('sub_entity', flat=True)
            # return a queryset limited to only those pks
            return self.filter(pk__in=entity_pks)
        else:
            return self

    def cache_relationships(self, cache_super=True, cache_sub=True):
        """
        Caches the super and sub relationships by doing a prefetch_related.
        """
        relationships_to_cache = compress(
            ['super_relationships__super_entity', 'sub_relationships__sub_entity'], [cache_super, cache_sub])
        return self.prefetch_related(*relationships_to_cache)


class AllEntityManager(ActivatableManager):
    """
    Provides additional entity-wide filtering abilities over all of the entity objects.
    """
    def get_queryset(self):
        return EntityQuerySet(self.model)

    def get_for_obj(self, entity_model_obj):
        """
        Given a saved entity model object, return the associated entity.
        """
        return self.get(entity_type=ContentType.objects.get_for_model(
            entity_model_obj, for_concrete_model=False), entity_id=entity_model_obj.id)

    def delete_for_obj(self, entity_model_obj):
        """
        Delete the entities associated with a model object.
        """
        return self.filter(
            entity_type=ContentType.objects.get_for_model(
                entity_model_obj, for_concrete_model=False), entity_id=entity_model_obj.id).delete(
            force=True)

    def active(self):
        """
        Returns active entities.
        """
        return self.get_queryset().active()

    def inactive(self):
        """
        Returns inactive entities.
        """
        return self.get_queryset().inactive()

    def is_any_kind(self, *entity_kinds):
        """
        Returns entities that have any of the kinds listed in entity_kinds.
        """
        return self.get_queryset().is_any_kind(*entity_kinds)

    def is_not_any_kind(self, *entity_kinds):
        """
        Returns entities that do not have any of the kinds listed in entity_kinds.
        """
        return self.get_queryset().is_not_any_kind(*entity_kinds)

    def is_sub_to_all_kinds(self, *super_entity_kinds):
        """
        Each returned entity will have superentites whos combined entity_kinds included *super_entity_kinds
        """
        return self.get_queryset().is_sub_to_all_kinds(*super_entity_kinds)

    def is_sub_to_any_kind(self, *super_entity_kinds):
        """
        Find all entities that have super_entities of any of the specified kinds
        """
        return self.get_queryset().is_sub_to_any_kind(*super_entity_kinds)

    def is_sub_to_all(self, *super_entities):
        """
        Given a list of super entities, return the entities that have those super entities as a subset of theirs.
        """
        return self.get_queryset().is_sub_to_all(*super_entities)

    def is_sub_to_any(self, *super_entities):
        """
        Given a list of super entities, return the entities whose super entities intersect with the provided super
        entities.
        """
        return self.get_queryset().is_sub_to_any(*super_entities)

    def cache_relationships(self, cache_super=True, cache_sub=True):
        """
        Caches the super and sub relationships by doing a prefetch_related.
        """
        return self.get_queryset().cache_relationships(cache_super=cache_super, cache_sub=cache_sub)


class ActiveEntityManager(AllEntityManager):
    """
    The default 'objects' on the Entity model. This manager restricts all Entity queries to happen over active
    entities.
    """
    def get_queryset(self):
        return EntityQuerySet(self.model).active()


@compare_on_attr()
class Entity(BaseActivatableModel):
    """
    Describes an entity and its relevant metadata. Also defines if the entity is active. Filtering functions
    are provided that mirror the filtering functions in the Entity model manager.
    """
    # A human-readable name for the entity
    display_name = models.TextField(blank=True, db_index=True)

    # The generic entity
    entity_id = models.IntegerField()
    entity_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    entity = GenericForeignKey('entity_type', 'entity_id')

    # The entity kind
    entity_kind = models.ForeignKey(EntityKind, on_delete=models.PROTECT)

    # Metadata about the entity, stored as JSON
    entity_meta = JSONField(null=True, encoder=DjangoJSONEncoder)

    # True if this entity is active
    is_active = models.BooleanField(default=True, db_index=True)

    objects = ActiveEntityManager()
    all_objects = AllEntityManager()

    class Meta:
        unique_together = ('entity_id', 'entity_type')

    def get_sub_entities(self):
        """
        Returns all of the sub entities of this entity. The returned entities may be filtered by chaining any
        of the functions in EntityFilter.
        """
        return [r.sub_entity for r in self.sub_relationships.all()]

    def get_super_entities(self):
        """
        Returns all of the super entities of this entity. The returned super entities may be filtered by
        chaining methods from EntityFilter.
        """
        return [r.super_entity for r in self.super_relationships.all()]

    def __str__(self):
        """Return the display_name field
        """
        return self.display_name


class EntityRelationship(models.Model):
    """
    Defines a relationship between two entities, telling which
    entity is a superior (or sub) to another entity. Similary, this
    model allows us to define if the relationship is active.
    """

    class Meta:
        unique_together = ('sub_entity', 'super_entity')

    # The sub entity. The related name is called super_relationships since
    # querying this reverse relationship returns all of the relationships
    # super to an entity
    sub_entity = models.ForeignKey(Entity, related_name='super_relationships', on_delete=models.CASCADE)

    # The super entity. The related name is called sub_relationships since
    # querying this reverse relationships returns all of the relationships
    # sub to an entity
    super_entity = models.ForeignKey(Entity, related_name='sub_relationships', on_delete=models.CASCADE)


class EntityGroupManager(models.Manager):

    def get_membership_cache(self, group_ids=None, is_active=True):
        """
        Build a dict cache with the group membership info. Keyed off the group id and the values are
        a 2 element list of entity id and entity kind id (same values as the membership model). If no group ids
        are passed, then all groups will be fetched

        :param is_active: Flag indicating whether to filter on entity active status. None will not filter.
        :rtype: dict
        """
        membership_queryset = EntityGroupMembership.objects.filter(
            Q(entity__isnull=True) | (Q(entity__isnull=False) & Q(entity__is_active=is_active))
        )
        if is_active is None:
            membership_queryset = EntityGroupMembership.objects.all()

        if group_ids:
            membership_queryset = membership_queryset.filter(entity_group_id__in=group_ids)

        membership_queryset = membership_queryset.values_list('entity_group_id', 'entity_id', 'sub_entity_kind_id')

        # Iterate over the query results and build the cache dict
        membership_cache = {}
        for entity_group_id, entity_id, sub_entity_kind_id in membership_queryset:
            membership_cache.setdefault(entity_group_id, [])
            membership_cache[entity_group_id].append([entity_id, sub_entity_kind_id])

        return membership_cache


class EntityGroup(models.Model):
    """
    An arbitrary group of entities and sub-entity groups.

    Members can be added to the group through the ``add_entity`` and
    ``bulk_add_entities`` methods, removed with the ``remove_entity``
    and ``bulk_remove_entities`` methods, as well as completely change
    the members of the group with the ``bulk_overwrite`` method.

    Since entity groups support inclusion of individual entities, as
    well as groups of sub-entities of a given kind, querying for all
    of the individual entities in the group could be challenging. For
    this reason the ``all_entities`` method is included, which will
    return all of the individual entities in a given group.
    """

    objects = EntityGroupManager()

    def all_entities(self, is_active=True):
        """
        Return all the entities in the group.

        Because groups can contain both individual entities, as well
        as whole groups of entities, this method acts as a convenient
        way to get a queryset of all the entities in the group.
        """
        return self.get_all_entities(return_models=True, is_active=is_active)

    def get_all_entities(self, membership_cache=None, entities_by_kind=None, return_models=False, is_active=True):
        """
        Returns a list of all entity ids in this group or optionally returns a queryset for all entity models.
        In order to reduce queries for multiple group lookups, it is expected that the membership_cache and
        entities_by_kind are built outside of this method and passed in as arguments.
        :param membership_cache: A group cache dict generated from `EntityGroup.objects.get_membership_cache()`
        :type membership_cache: dict
        :param entities_by_kind: An entities by kind dict generated from the `get_entities_by_kind` function
        :type entities_by_kind: dict
        :param return_models: If True, returns an Entity queryset, if False, returns a set of entity ids
        :type return_models: bool
        :param is_active: Flag to control entities being returned. Defaults to True for active entities only
        :type is_active: bool
        """
        # If cache args were not passed, generate the cache
        if membership_cache is None:
            membership_cache = EntityGroup.objects.get_membership_cache([self.id], is_active=is_active)

        if entities_by_kind is None:
            entities_by_kind = entities_by_kind or get_entities_by_kind(membership_cache=membership_cache)

        # Build set of all entity ids for this group
        entity_ids = set()

        # This group does have entities
        if membership_cache.get(self.id):

            # Loop over each membership in this group
            for entity_id, entity_kind_id in membership_cache[self.id]:
                if entity_id:
                    if entity_kind_id:
                        # All sub entities of this kind under this entity
                        entity_ids.update(entities_by_kind[entity_kind_id][entity_id])
                    else:
                        # Individual entity
                        entity_ids.add(entity_id)
                else:
                    # All entities of this kind
                    entity_ids.update(entities_by_kind[entity_kind_id]['all'])

        # Check if a queryset needs to be returned
        if return_models:
            return Entity.objects.filter(id__in=entity_ids)

        return entity_ids

    def add_entity(self, entity, sub_entity_kind=None):
        """
        Add an entity, or sub-entity group to this EntityGroup.

        :type entity: Entity
        :param entity: The entity to add.

        :type sub_entity_kind: Optional EntityKind
        :param sub_entity_kind: If a sub_entity_kind is given, all
            sub_entities of the entity will be added to this
            EntityGroup.
        """
        membership = EntityGroupMembership.objects.create(
            entity_group=self,
            entity=entity,
            sub_entity_kind=sub_entity_kind,
        )
        return membership

    def bulk_add_entities(self, entities_and_kinds):
        """
        Add many entities and sub-entity groups to this EntityGroup.

        :type entities_and_kinds: List of (Entity, EntityKind) pairs.
        :param entities_and_kinds: A list of entity, entity-kind pairs
            to add to the group. In the pairs the entity-kind can be
            ``None``, to add a single entity, or some entity kind to
            add all sub-entities of that kind.
        """
        memberships = [EntityGroupMembership(
            entity_group=self,
            entity=entity,
            sub_entity_kind=sub_entity_kind,
        ) for entity, sub_entity_kind in entities_and_kinds]
        created = EntityGroupMembership.objects.bulk_create(memberships)
        return created

    def remove_entity(self, entity, sub_entity_kind=None):
        """
        Remove an entity, or sub-entity group to this EntityGroup.

        :type entity: Entity
        :param entity: The entity to remove.

        :type sub_entity_kind: Optional EntityKind
        :param sub_entity_kind: If a sub_entity_kind is given, all
            sub_entities of the entity will be removed from this
            EntityGroup.
        """
        EntityGroupMembership.objects.get(
            entity_group=self,
            entity=entity,
            sub_entity_kind=sub_entity_kind,
        ).delete()

    def bulk_remove_entities(self, entities_and_kinds):
        """
        Remove many entities and sub-entity groups to this EntityGroup.

        :type entities_and_kinds: List of (Entity, EntityKind) pairs.
        :param entities_and_kinds: A list of entity, entity-kind pairs
            to remove from the group. In the pairs, the entity-kind
            can be ``None``, to add a single entity, or some entity
            kind to add all sub-entities of that kind.
        """
        criteria = [
            Q(entity=entity, sub_entity_kind=entity_kind)
            for entity, entity_kind in entities_and_kinds
        ]
        criteria = reduce(lambda q1, q2: q1 | q2, criteria, Q())
        EntityGroupMembership.objects.filter(
            criteria, entity_group=self).delete()

    def bulk_overwrite(self, entities_and_kinds):
        """
        Update the group to the given entities and sub-entity groups.

        After this operation, the only members of this EntityGroup
        will be the given entities, and sub-entity groups.

        :type entities_and_kinds: List of (Entity, EntityKind) pairs.
        :param entities_and_kinds: A list of entity, entity-kind pairs
            to set to the EntityGroup. In the pairs the entity-kind
            can be ``None``, to add a single entity, or some entity
            kind to add all sub-entities of that kind.
        """
        EntityGroupMembership.objects.filter(entity_group=self).delete()
        return self.bulk_add_entities(entities_and_kinds)


@compare_on_attr()
class AllEntityProxy(Entity):
    """
    This is a proxy of the entity class that makes the .objects attribute
    access all of the entities regardless of active state.  Active entities
    are accessed with the active_objects manager.  This proxy should be used
    when you need foreign-key relationships to be able to access all entities
    regardless of active state.
    """
    objects = AllEntityManager()
    active_objects = ActiveEntityManager()

    class Meta:
        proxy = True


class EntityGroupMembership(models.Model):
    """
    Membership information for entity groups.

    This model should usually not be queried/updated directly, but
    accessed through the EntityGroup api.

    When entity is null, it means all entities of the sub_entity_kind will be selected.
    When sub_entity_kind is null, only the specified entity will be selected.
    When entity and sub_entity_kind are both not null, it means all sub entities below 'entity'
    with a kind of 'sub_entity_kind' will be selected.
    """
    entity_group = models.ForeignKey(EntityGroup, on_delete=models.CASCADE)
    entity = models.ForeignKey(Entity, null=True, on_delete=models.CASCADE)
    sub_entity_kind = models.ForeignKey(EntityKind, null=True, on_delete=models.CASCADE)


def get_entities_by_kind(membership_cache=None, is_active=True):
    """
    Builds a dict with keys of entity kinds if and values are another dict. Each of these dicts are keyed
    off of a super entity id and optional have an 'all' key for any group that has a null super entity.
    Example structure:
    {
        entity_kind_id: {
            entity1_id: [1, 2, 3],
            entity2_id: [4, 5, 6],
            'all': [1, 2, 3, 4, 5, 6]
        }
    }

    :rtype: dict
    """
    # Accept an existing cache or build a new one
    if membership_cache is None:
        membership_cache = EntityGroup.objects.get_membership_cache(is_active=is_active)

    entities_by_kind = {}
    kinds_with_all = set()
    kinds_with_supers = set()
    super_ids = set()

    # Loop over each group
    for group_id, memberships in membership_cache.items():

        # Look at each membership
        for entity_id, entity_kind_id in memberships:

            # Only care about memberships with entity kind
            if entity_kind_id:

                # Make sure a dict exists for this kind
                entities_by_kind.setdefault(entity_kind_id, {})

                # Check if this is all entities of a kind under a specific entity
                if entity_id:
                    entities_by_kind[entity_kind_id][entity_id] = []
                    kinds_with_supers.add(entity_kind_id)
                    super_ids.add(entity_id)
                else:
                    # This is all entities of this kind
                    entities_by_kind[entity_kind_id]['all'] = []
                    kinds_with_all.add(entity_kind_id)

    # Get entities for 'all'
    all_entities_for_types = Entity.objects.filter(
        entity_kind_id__in=kinds_with_all
    ).values_list('id', 'entity_kind_id')

    # Add entity ids to entity kind's all list
    for id, entity_kind_id in all_entities_for_types:
        entities_by_kind[entity_kind_id]['all'].append(id)

    # Get relationships
    relationships = EntityRelationship.objects.filter(
        super_entity_id__in=super_ids,
        sub_entity__entity_kind_id__in=kinds_with_supers
    ).values_list(
        'super_entity_id', 'sub_entity_id', 'sub_entity__entity_kind_id'
    )

    # Add entity ids to each super entity's list
    for super_entity_id, sub_entity_id, sub_entity__entity_kind_id in relationships:
        entities_by_kind[sub_entity__entity_kind_id].setdefault(super_entity_id, [])
        entities_by_kind[sub_entity__entity_kind_id][super_entity_id].append(sub_entity_id)

    return entities_by_kind
