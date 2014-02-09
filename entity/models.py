from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.db import models


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
    entity_meta = models.TextField()
    # True if this entity is active
    is_active = models.BooleanField(default=True)


class EntityRelationship(models.Model):
    """
    Defines a relationship between two entities, telling which
    entity is a superior (or sub) to another entity. Similary, this
    model allows us to define if the relationship is active.
    """
    # The sub entity
    sub_entity = models.ForeignKey(Entity, related_name='+')
    # The super entity
    super_entity = models.ForeignKey(Entity, related_name='+')
    # True if the relationshp is active
    is_active = models.BooleanField(default=True)
