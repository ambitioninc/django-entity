from django.db import models

from entity import BaseEntityModel, Entity
from entity.models import EntityModelManager
from manager_utils import ManagerUtilsManager


class TeamGroup(BaseEntityModel):
    """
    A grouping of teams.
    """
    name = models.CharField(max_length=256)


class Competitor(BaseEntityModel):
    """
    An enclosing group for competitors
    """
    pass


class TeamManager(ManagerUtilsManager):
    def get_queryset(self):
        return super(TeamManager, self).get_queryset().select_related('team_group')


class Team(BaseEntityModel):
    """
    A team entity model. Encapsulates accounts.
    """
    name = models.CharField(max_length=256)
    # Used for testing if the entity is active
    is_active = models.BooleanField(default=True)
    # Used for additional super entity tests
    team_group = models.ForeignKey(TeamGroup, null=True)

    objects = TeamManager()

    def is_entity_active(self):
        return self.is_active

    def get_super_entities(self):
        return [self.team_group] if self.team_group is not None else []


class AccountManager(ManagerUtilsManager):
    def get_queryset(self):
        return super(AccountManager, self).get_queryset().select_related('team', 'team2', 'team_group', 'competitor')


class Account(BaseEntityModel):
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
    # The second team that the account is on
    team2 = models.ForeignKey(Team, null=True, related_name='+')
    # The team group
    team_group = models.ForeignKey(TeamGroup, null=True)
    # The comptetitor group
    competitor = models.ForeignKey(Competitor, null=True)

    objects = AccountManager()

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
        super_entities = []
        if self.team is not None:
            super_entities.append(self.team)
        if self.team2 is not None:
            super_entities.append(self.team2)
        if self.team_group is not None:
            super_entities.append(self.team_group)
        if self.competitor is not None:
            super_entities.append(self.competitor)
        return super_entities


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

    objects = EntityModelManager()


class BaseEntityClass(BaseEntityModel):
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
