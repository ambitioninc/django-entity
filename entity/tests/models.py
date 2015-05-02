from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from entity.config import EntityConfig, entity_registry, register_entity
from entity.models import Entity
from manager_utils import ManagerUtilsManager


class BaseEntityModel(models.Model):
    class Meta:
        abstract = True

    objects = ManagerUtilsManager()


@python_2_unicode_compatible
class TeamGroup(BaseEntityModel):
    """
    A grouping of teams.
    """
    name = models.CharField(max_length=256)

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class Competitor(BaseEntityModel):
    """
    An enclosing group for competitors
    """
    name = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Team(BaseEntityModel):
    """
    A team entity model. Encapsulates accounts.
    """
    name = models.CharField(max_length=256)
    # Used for testing if the entity is active
    is_active = models.BooleanField(default=True)
    # Used for additional super entity tests
    team_group = models.ForeignKey(TeamGroup, null=True)


@python_2_unicode_compatible
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

    def __str__(self):
        return self.email


class M2mEntity(BaseEntityModel):
    """
    Used for testing syncing of a model with a M2M.
    """
    teams = models.ManyToManyField(Team)


class PointsToM2mEntity(BaseEntityModel):
    """
    A model that points to an m2mentity. Used to recreate the scenario when an account
    points to a user that is included in a group.
    """
    m2m_entity = models.OneToOneField(M2mEntity)


class PointsToAccount(BaseEntityModel):
    account = models.ForeignKey(Account)


class EntityPointer(BaseEntityModel):
    """
    Describes a test model that points to an entity. Used for ensuring
    that syncing entities doesn't perform any Entity deletes (causing models like
    this to be cascade deleted)
    """
    entity = models.ForeignKey(Entity)


class DummyModel(BaseEntityModel):
    """
    Used to ensure that models that don't register for entity syncing aren't synced.
    """
    dummy_data = models.CharField(max_length=64)

    objects = ManagerUtilsManager()


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


@register_entity(Account.objects.select_related('team', 'team2', 'team_group', 'competitor'))
class AccountConfig(EntityConfig):
    """
    Entity configuration for the account model
    """
    def get_is_active(self, model_obj):
        return model_obj.is_active

    def get_entity_meta(self, model_obj):
        """
        Returns metadata about the account that will be serialized
        in the mirrored entity tables.
        """
        return {
            'email': model_obj.email,
            'team': model_obj.team.name if model_obj.team else None,
            'is_captain': model_obj.is_captain,
            'team_is_active': model_obj.team.is_active if model_obj.team else None,
        }

    def get_super_entities(self, model_obj):
        """
        Gets the super entities this entity belongs to.
        """
        super_entities = []
        if model_obj.team is not None:
            super_entities.append(model_obj.team)
        if model_obj.team2 is not None:
            super_entities.append(model_obj.team2)
        if model_obj.team_group is not None:
            super_entities.append(model_obj.team_group)
        if model_obj.competitor is not None and model_obj.competitor.is_active:
            super_entities.append(model_obj.competitor)

        return super_entities


@register_entity(Team.objects.select_related('team_group'))
class TeamConfig(EntityConfig):
    def get_is_active(self, model_obj):
        return model_obj.is_active

    def get_super_entities(self, model_obj):
        return [model_obj.team_group] if model_obj.team_group is not None else []

    def get_display_name(self, model_obj):
        return 'team'


@register_entity(M2mEntity.objects.prefetch_related('teams'))
class M2mEntityConfig(EntityConfig):
    def get_super_entities(self, model_obj):
        return model_obj.teams.all()


@register_entity(PointsToM2mEntity.objects.prefetch_related('m2m_entity__teams'))
class PointsToM2mEntityConfig(EntityConfig):
    watching = [
        (M2mEntity, lambda m2m_entity_obj: PointsToM2mEntity.objects.filter(m2m_entity=m2m_entity_obj)),
    ]

    def get_super_entities(self, model_obj):
        return model_obj.m2m_entity.teams.all()


@register_entity(PointsToAccount)
class PointsToAccountConfig(EntityConfig):
    watching = [
        (Competitor, lambda competitor_obj: PointsToAccount.objects.filter(account__competitor=competitor_obj)),
        (Team, lambda team_obj: PointsToAccount.objects.filter(account__team=team_obj)),
    ]

    def get_entity_meta(self, model_obj):
        return {
            'competitor_name': model_obj.account.competitor.name if model_obj.account.competitor else 'None',
            'team_name': model_obj.account.team.name if model_obj.account.team else 'None',
        }


# Register the test models here. TODO - figure out why django does not like having these functions in
# the tests/models.py file
entity_registry.register_entity(TeamGroup)
entity_registry.register_entity(Competitor)
entity_registry.register_entity(MultiInheritEntity)
