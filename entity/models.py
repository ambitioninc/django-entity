from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from jsonfield import JSONField
from manager_utils import ManagerUtilsManager, post_bulk_operation

from .entity_filter import EntityFilter


class EntityManager(ManagerUtilsManager):
    """
    Provides additional entity-wide filtering abilities.
    """
    def get_for_obj(self, entity_model_obj):
        """
        Given a saved entity model object, return the associated entity.
        """
        return self.get(entity_type=ContentType.objects.get_for_model(entity_model_obj), entity_id=entity_model_obj.id)


class CachedEntityManager(EntityManager):
    """
    Prefetches relationship information so that filtering on entities doesn't result in additional
    database queries.
    """
    def get_queryset(self):
        return super(CachedEntityManager, self).get_queryset().prefetch_related(
            'super_relationships__super_entity', 'sub_relationships__sub_entity')


class Entity(models.Model):
    """
    Describes an entity and its relevant metadata. Also defines
    if the entity is active.
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
    cached_objects = CachedEntityManager()

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


class EntityModelMixin(object):
    """
    Provides functionality needed for apps that wish to mirror entities.
    Any app that wishes to mirror an entity must make the model inherit
    this mixin class. It is up to the user to override the necessary
    function in this model (or leave them as defaults).

    Similarly, this class provides additional functions that Entity models
    will receive, such as the ability to quickly retrieve super and
    subentities.
    """
    def get_entity_meta(self):
        """
        Retrieves metadata about an entity.

        Returns:
            A dictionary of metadata about an entity or None if there is no
            metadata. Defaults to returning None
        """
        return None

    def is_entity_active(self):
        """
        Describes if the entity is currently active.

        Returns:
            A Boolean specifying if the entity is active. Defaults to
            returning True.
        """
        return True

    def get_super_entities(self):
        """
        Retrieves a list of all entities that have a "super" relationship with the
        entity.

        Returns:
            A list of models. If there are no super entities, return a empty list.
            Defaults to returning an empty list.
        """
        return []


class EntityModelManager(ManagerUtilsManager):
    """
    Provides the ability to prefetch entity relationships so that filtering operations happen
    quickly on them.
    """
    pass


class BaseEntityModel(models.Model, EntityModelMixin):
    """
    Defines base properties for an Entity model defined by a third-party application.
    """
    class Meta:
        abstract = True

    objects = EntityModelManager()


def sync_entity_signal_handler(sender, model_obj, is_deleted):
    """
    Filters post save/delete signals for entities by checking if they
    inherit EntityModelMixin. If so, the model is synced to the entity
    table.
    """
    if issubclass(sender, EntityModelMixin):
        # Include the function here to avoid circular dependencies
        from .sync import sync_entity
        sync_entity(model_obj, is_deleted)


def sync_entities_signal_handler(sender):
    """
    When a bulk operation occurs on a model manager, sync all the entities
    if the model of the manager is an entity class.
    """
    if issubclass(sender.model, EntityModelMixin):
        from .sync import sync_entities
        sync_entities()


@receiver(post_delete, dispatch_uid='delete_entity_signal_handler')
def delete_entity_signal_handler(sender, *args, **kwargs):
    """
    Defines a signal handler for syncing an individual entity. Called when
    an entity is saved or deleted.
    """
    sync_entity_signal_handler(sender, kwargs['instance'], True)


@receiver(post_save, dispatch_uid='save_entity_signal_handler')
def save_entity_signal_handler(sender, *args, **kwargs):
    """
    Defines a signal handler for saving an entity. Syncs the entity to
    the entity mirror table.
    """
    sync_entity_signal_handler(sender, kwargs['instance'], False)


@receiver(post_bulk_operation, dispatch_uid='bulk_operation_signal_handler')
def bulk_operation_signal_handler(sender, *args, **kwargs):
    """
    When a bulk operation has happened on a model, sync all the entities again.
    """
    sync_entities_signal_handler(sender)
