from django.db import models

from entity.models import EntityModelMixin, Entity



class Team(models.Model, EntityModelMixin):
    """
    A team entity model. Encapsulates accounts.
    """
    name = models.CharField(max_length=256)
    # Used for testing if the entity is active
    is_active = models.BooleanField(default=True)

    def is_entity_active(self):
        return self.is_active


class Account(models.Model, EntityModelMixin):
    """
    An account entity model
    """
    email = models.CharField(max_length=256)
    # Used for testing if the entity is active
    is_active = models.BooleanField(default=True)
    # Team is a super entity for an account
    team = models.ForeignKey(Team, null=True)
    # True if the account is a captain of its team
    is_captain = models.BooleanField(default=False)

    def is_entity_active(self):
        return self.is_active

    def get_entity_meta(self):
        """
        Returns metadata about the account that will be serialized
        in the mirrored entity tables.
        """
        return {
            'email': self.email,
            'team': self.team.name if self.team else None,
            'is_captain': self.is_captain,
        }

    def get_super_entities(self):
        """
        Gets the super entities this entity belongs to.
        """
        return [self.team] if self.team is not None else []

    def is_super_entity_relationship_active(self, super_entity):
        """
        Make it an inactive relationship when the account is a captain
        of a team.
        """
        return not self.is_captain


class EntityPointer(models.Model):
    """
    Describes a test model that points to an entity. Used for ensuring
    that operations on entities (such as updates) don't cause
    side effects of having a pointer to an entity.
    """
    entity = models.ForeignKey(Entity)
