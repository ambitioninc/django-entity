from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Count
from django.db.models.signals import post_save, post_delete
from jsonfield import JSONField
from manager_utils import ManagerUtilsManager, ManagerUtilsQuerySet, post_bulk_operation

from entity.entity_filter import EntityFilter
from entity import entity_registry


class EntityQuerySet(ManagerUtilsQuerySet):
    """
    Provides additional queryset filtering abilities.
    """
    def has_super_entity_subset(self, *super_entities):
        """
        Given a list of super entities, return the entities that have those as a subset of their super entities.
        """
        if super_entities:
            # Get a list of entities that have super entities with all types
            has_subset = EntityRelationship.objects.filter(
                super_entity__in=super_entities).values('sub_entity').annotate(Count('super_entity')).filter(
                super_entity__count=len(set(super_entities))).values_list('sub_entity', flat=True)

            return self.filter(id__in=has_subset)
        else:
            return self

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

    def is_type(self, *entity_types):
        """
        Returns entities that have any of the types listed in entity_types.
        """
        return self.filter(entity_type__in=entity_types) if entity_types else self

    def is_not_type(self, *entity_types):
        """
        Returns entities that are not any of the types listed in entity_types.
        """
        return self.exclude(entity_type__in=entity_types) if entity_types else self

    def cache_relationships(self):
        """
        Caches the super and sub relationships by doing a prefetch_related.
        """
        return self.prefetch_related('super_relationships__super_entity', 'sub_relationships__sub_entity')


class EntityManager(ManagerUtilsManager):
    """
    Provides additional entity-wide filtering abilities.
    """
    def get_queryset(self):
        return EntityQuerySet(self.model)

    def get_for_obj(self, entity_model_obj):
        """
        Given a saved entity model object, return the associated entity.
        """
        return self.get(entity_type=ContentType.objects.get_for_model(entity_model_obj), entity_id=entity_model_obj.id)

    def delete_for_obj(self, entity_model_obj):
        """
        Delete the entity associated with a model object.
        """
        return self.filter(
            entity_type=ContentType.objects.get_for_model(entity_model_obj), entity_id=entity_model_obj.id).delete()

    def has_super_entity_subset(self, *super_entities):
        """
        Given a list of super entities, return the entities that have those super entities as a subset of theirs.
        """
        return self.get_queryset().has_super_entity_subset(*super_entities)

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

    def is_type(self, *entity_types):
        """
        Returns entities that have any of the types listed in entity_types.
        """
        return self.get_queryset().is_type(*entity_types)

    def is_not_type(self, *entity_types):
        """
        Returns entities that are not any of the types listed in entity_types.
        """
        return self.get_queryset().is_not_type(*entity_types)

    def cache_relationships(self):
        """
        Caches the super and sub relationships by doing a prefetch_related.
        """
        return self.get_queryset().cache_relationships()


class Entity(models.Model):
    """
    Describes an entity and its relevant metadata. Also defines if the entity is active. Filtering functions
    are provided that mirror the filtering functions in the Entity model manager.
    """
    # The generic entity
    entity_id = models.IntegerField()
    entity_type = models.ForeignKey(ContentType)
    entity = generic.GenericForeignKey('entity_type', 'entity_id')
    # Metadata about the entity, stored as JSON
    entity_meta = JSONField(null=True)
    # True if this entity is active
    is_active = models.BooleanField(default=True)
    objects = EntityManager()

    def get_sub_entities(self):
        """
        Returns all of the sub entities of this entity. The returned entities may be filtered by chaining any
        of the functions in EntityFilter.
        """
        return EntityFilter(r.sub_entity for r in self.sub_relationships.all())

    def get_super_entities(self):
        """
        Returns all of the super entities of this entity. The returned super entities may be filtered by
        chaining methods from EntityFilter.
        """
        return EntityFilter(r.super_entity for r in self.super_relationships.all())

    def active(self):
        """
        Returns True if the entity is active.
        """
        return self.is_active is True

    def inactive(self):
        """
        Returns True if the entity is inactive.
        """
        return self.is_active is False

    def is_type(self, *entity_types):
        """
        Returns True if the entity's type is in any of the types given. If no entity types are given,
        returns True.
        """
        return self.entity_type_id in (entity_type.id for entity_type in entity_types) if entity_types else True

    def is_not_type(self, *entity_types):
        """
        Returns True if the entity's type is not in any of the types given. If no entity types are given,
        returns True.
        """
        return self.entity_type_id not in (entity_type.id for entity_type in entity_types)

    def has_super_entity_subset(self, *super_entities):
        """
        Returns True if the super entities are a subset of the entity's super entities.
        """
        return set(super_entities).issubset(self.get_super_entities())


class EntityRelationship(models.Model):
    """
    Defines a relationship between two entities, telling which
    entity is a superior (or sub) to another entity. Similary, this
    model allows us to define if the relationship is active.
    """
    # The sub entity. The related name is called super_relationships since
    # querying this reverse relationship returns all of the relationships
    # super to an entity
    sub_entity = models.ForeignKey(Entity, related_name='super_relationships')
    # The super entity. The related name is called sub_relationships since
    # querying this reverse relationships returns all of the relationships
    # sub to an entity
    super_entity = models.ForeignKey(Entity, related_name='sub_relationships')


def delete_entity_signal_handler(sender, *args, **kwargs):
    """
    Defines a signal handler for syncing an individual entity. Called when
    an entity is saved or deleted.
    """
    if sender in entity_registry.entity_registry:
        Entity.objects.delete_for_obj(kwargs['instance'])


def save_entity_signal_handler(sender, *args, **kwargs):
    """
    Defines a signal handler for saving an entity. Syncs the entity to
    the entity mirror table.
    """
    if sender in entity_registry.entity_registry:
        from entity.sync import sync_entities
        sync_entities(kwargs['instance'])


def bulk_operation_signal_handler(sender, *args, **kwargs):
    """
    When a bulk operation has happened on a model, sync all the entities again.
    NOTE - bulk syncing isn't turned on by default because of the consequences of it.
    For example, a user may issue a simple update to a single model, which would trigger
    syncing of all entities. It is up to the user to explicitly enable syncing on bulk
    operations with turn_on_syncing(bulk=True)
    """
    if sender.model in entity_registry.entity_registry:
        from entity.sync import sync_entities
        sync_entities()


def turn_off_syncing():
    """
    Disables all of the signals for syncing entities. If bulk is True, disable syncing on bulk operations.
    """
    post_delete.disconnect(delete_entity_signal_handler, dispatch_uid='delete_entity_signal_handler')
    post_save.disconnect(save_entity_signal_handler, dispatch_uid='save_entity_signal_handler')
    post_bulk_operation.disconnect(bulk_operation_signal_handler, dispatch_uid='bulk_operation_signal_handler')


def turn_on_syncing(bulk=False):
    """
    Enables all of the signals for syncing entities. If bulk is True, enable syncing on bulk operations.
    """
    post_delete.connect(delete_entity_signal_handler, dispatch_uid='delete_entity_signal_handler')
    post_save.connect(save_entity_signal_handler, dispatch_uid='save_entity_signal_handler')
    if bulk:
        post_bulk_operation.connect(bulk_operation_signal_handler, dispatch_uid='bulk_operation_signal_handler')


# Connect all default signal handlers
turn_on_syncing()
