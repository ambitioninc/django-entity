from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from jsonfield import JSONField


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

    def passes_is_active(self, filtered_relationship, filtered_entity, is_active):
        """
        Returns True if the relationship and its relating sub entity is active based on the
        is_active flag. If is_active is True, both the relationship and the relating entity
        have to be active. If is_active is False, the relationship or relating entity
        has to be inactive in order to pass the filter.

        Args:
            is_active: Specifies the active flag upon which to filter. If None, this function
                always passes (i.e returns True). If True, both the relationship and relating
                entity have to be active. If False, either the relationship or the relating
                entity has to be False to pass.
            filtered_relationship: An EntityRelationship model.
            filtered_entity: The relating entity to filter based on activity.

        Returns:
            True if the is_active filter passes, False otherwise.
        """
        return is_active is None or is_active == (filtered_entity.is_active and filtered_relationship.is_active)

    def passes_entity_type(self, filtered_entity, entity_type):
        """
        Returns True if the filtered_entity is of type entity_type, False otherwise. If entity_type
        is None, it always return True.

        Args:
            filtered_entity: The Entity model being filtered.
            entity_type: A Django ContentType or None if there is no filter.

        Returns:
            True if the filtered_entity is of type entity_type or entity_type is None, False otherwise.
        """
        return entity_type is None or filtered_entity.entity_type == entity_type

    def get_sub_entities(self, is_active=None, entity_type=None):
        """
        Returns all of the sub entities of this entity.

        Args:
            is_active: Specifies how to filter active vs inactive relationships. If is_active is None, return all
                retlationships. If False, return only inactive relationships. If True, return all active
                relationships. Defaults to None. Note that even if a relationship is active, if the entity
                is inactive, it will not be returned when is_active=True.
            entity_type: Only returns sub entities of the given Django ContentType. If None, no filtering
                is done.

        Returns:
            A list of Entity models or an empty list if there are no sub entities.
        """
        # Note - do a naive filtering on the entire sub_relationships set.
        # This provides any other code with the ability to use django's
        # prefetch related on the sub or super_relationships sets.
        return [
            r.sub_entity for r in self.sub_relationships.all()
            if self.passes_is_active(r, r.sub_entity, is_active) and self.passes_entity_type(r.sub_entity, entity_type)
        ]

    def get_super_entities(self, is_active=None, entity_type=None):
        """
        Returns all of the super entities of this entity.

        Args:
            is_active: Specifies how to filter active vs inactive relationships. If is_active is None, return all
                retlationships. If False, return only inactive relationships. If True, return all active
                relationships. Defaults to None. Note that even if a relationship is active, if the entity
                is inactive, it will not be returned when is_active=True.
            entity_type: Only returns super entities of the given Django ContentType. If None, no filtering
                is done.

        Returns:
            A list of Entity models or an empty list if there are no super entities.
        """
        # Note - do a naive filtering on the entire super_relationships set.
        # This provides any other code with the ability to use django's
        # prefetch related on the sub or super_relationships sets.
        return [
            r.super_entity for r in self.super_relationships.all()
            if (self.passes_is_active(r, r.super_entity, is_active) and
                self.passes_entity_type(r.super_entity, entity_type))
        ]


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
    # True if the relationship is active
    is_active = models.BooleanField(default=True)


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

    def is_super_entity_relationship_active(self, model_obj):
        """
        Given a model object, return True if the entity has an active relationship
        with that super entity model object.

        Args:
            model_obj - An model object that is a super entity of the entity.

        Returns:
            A Boolean describing if the activity of the relationship with model_obj.
            Defaults to returning True.
        """
        return True


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


@receiver(post_delete)
def delete_entity_signal_handler(sender, *args, **kwargs):
    """
    Defines a signal handler for syncing an individual entity. Called when
    an entity is saved or deleted.
    """
    sync_entity_signal_handler(sender, kwargs['instance'], True)


@receiver(post_save)
def save_entity_signal_handler(sender, *args, **kwargs):
    """
    Defines a signal handler for saving an entity. Syncs the entity to
    the entity mirror table.
    """
    sync_entity_signal_handler(sender, kwargs['instance'], False)
