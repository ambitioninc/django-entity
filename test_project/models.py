from django.db import models

from entity import EntityModelMixin, Entity


class TeamGroup(models.Model, EntityModelMixin):
    """
    A grouping of teams.
    """
    name = models.CharField(max_length=256)


class Team(models.Model, EntityModelMixin):
    """
    A team entity model. Encapsulates accounts.
    """
    name = models.CharField(max_length=256)
    # Used for testing if the entity is active
    is_active = models.BooleanField(default=True)
    # Used for additional super entity tests
    team_group = models.ForeignKey(TeamGroup, null=True)

    def is_entity_active(self):
        return self.is_active

    def get_super_entities(self):
        return [self.team_group] if self.team_group is not None else []


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
    that syncing entities doesn't perform any Entity deletes (causing models like
    this to be cascade deleted)
    """
    entity = models.ForeignKey(Entity)


class DummyModel(models.Model):
    """
    Used to ensure that models that don't inherit from EntityModelMixin aren't syned.
    """
    dummy_data = models.CharField(max_length=64)


class BaseEntityClass(models.Model, EntityModelMixin):
    """
    A base class that inherits EntityModelMixin. Helps ensure that mutliple-inherited
    entities are still synced properly.
    """
    class Meta:
        abstract = True


class MultiInheritEntity(BaseEntityClass):
    """
    Verifies that entities that dont directly inherit from the EntityModelMixin are
    still synced properly.
    """
    data = models.CharField(max_length=64)
