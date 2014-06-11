from django.contrib.contenttypes.models import ContentType
from entity.models import Entity, EntityRelationship

from .models import Account, Team, TeamGroup
from .utils import EntityTestCase


class EntityFilteringTest(EntityTestCase):
    """
    Tests the EntityFilter class for filtering entities.
    """
    def setUp(self):
        super(EntityFilteringTest, self).setUp()
        self.account_type = ContentType.objects.get_for_model(Account)
        self.team_type = ContentType.objects.get_for_model(Team)

    def test_has_super_entity_subset_none(self):
        """
        Tests the has_super_entity_subset function on entities that have no super entities.
        """
        # Create a team and an account
        team_group = TeamGroup.objects.create()
        team_group_entity = Entity.objects.get_for_obj(team_group)
        team = Team.objects.create(team_group=team_group)
        account = Account.objects.create(team=team, team_group=team_group)
        # Get the entity of the account and the team
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        # Test that subset with no super entites returns the team and team group
        self.assertEquals(
            list(account_entity.get_super_entities().is_sub_to_all()),
            [team_entity, team_group_entity])

    def test_has_super_entity_subset_one(self):
        """
        Tests the has_super_entity_subset function on entities with one super entity.
        """
        # Create a team, team group, and an account for testing
        team_group = TeamGroup.objects.create()
        team = Team.objects.create(team_group=team_group)
        account = Account.objects.create(team=team)
        # Get the entity of the account and the team
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        team_group_entity = Entity.objects.get_for_obj(team_group)
        # Test that subset with the team group entity results in the team
        self.assertEquals(
            list(account_entity.get_super_entities().is_sub_to_all(team_group_entity)),
            [team_entity])

    def test_has_super_entity_subset_two(self):
        """
        Tests the has_super_entity_subset function on entities with two super entities.
        """
        # Create a team, team group, and an account for testing
        team_group = TeamGroup.objects.create()
        team = Team.objects.create(team_group=team_group)
        account = Account.objects.create(team=team, team_group=team_group)
        # Get the entity of the account and the team
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        team_group_entity = Entity.objects.get_for_obj(team_group)
        # Test that subset with the team and team group results in nothing since no objects have those
        # super entities
        self.assertEquals(
            list(account_entity.get_super_entities().is_sub_to_all(team_entity, team_group_entity)),
            [])
        # Test that performing the same subset on the account returns True
        self.assertTrue(account_entity.is_sub_to_all(team_entity, team_group_entity))

    def test_get_active_sub_entities_relationships_one(self):
        """
        Tests retrieval of all active sub entities when one exists.
        """
        # Create a team and an account with the team as a super entity.
        team = Team.objects.create()
        account = Account.objects.create(team=team)
        # Get the entity of the account and the team
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        # Verify that the active sub entities of the team is the account
        self.assertEquals(list(team_entity.get_sub_entities().active()), [account_entity])
        # Verify that the inactive sub entities of the team is nothing
        self.assertEquals(list(team_entity.get_sub_entities().inactive()), [])

    def test_get_inactive_sub_entities_one(self):
        """
        Tests retrieval of all inactive sub entities when one exists.
        """
        # Create a team and an account with the team as a super entity. Make the relationship
        # active but the entity inactive
        team = Team.objects.create()
        account = Account.objects.create(team=team, is_active=False)
        # Get the entity of the account and the team
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        # Verify that the active sub entities of the team is nothing
        self.assertEquals(list(team_entity.get_sub_entities().active()), [])
        # Verify that the inactive sub entities of the team is the account
        self.assertEquals(list(team_entity.get_sub_entities().inactive()), [account_entity])

    def test_get_active_super_entities_relationships_one(self):
        """
        Tests retrieval of all active super entities when one exists.
        """
        # Create a team and an account with the team as a super entity.
        team = Team.objects.create()
        account = Account.objects.create(team=team)
        # Get the entity of the account and the team
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        # Verify that the active super entities of the account is the team
        self.assertEquals(list(account_entity.get_super_entities().active()), [team_entity])
        # Verify that the inactive super entities of the account is nothing
        self.assertEquals(list(account_entity.get_super_entities().inactive()), [])

    def test_get_inactive_super_entities_one(self):
        """
        Tests retrieval of all inactive super entities when one exists.
        """
        # Create a team and an account with the team as a super entity. Make the relationship
        # active but the entity inactive
        team = Team.objects.create(is_active=False)
        account = Account.objects.create(team=team)
        # Get the entity of the account and the team
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        # Verify that the active super entities of the team is nothing
        self.assertEquals(list(account_entity.get_sub_entities().active()), [])
        # Verify that the inactive suoer entities of the account is the team
        self.assertEquals(list(account_entity.get_super_entities().inactive()), [team_entity])

    def test_default_entity_relationship_is_active(self):
        """
        Tests that the default entity relationships are set to active
        """
        team_group = TeamGroup.objects.create(name='Group')
        team = Team.objects.create(name='Team', team_group=team_group)
        team_entity = Entity.objects.get_for_obj(team)
        team_group_entity = Entity.objects.get_for_obj(team_group)
        # Verify that the team has an active relationship with its super entity
        EntityRelationship.objects.get(sub_entity=team_entity, super_entity=team_group_entity)

    def test_is_type_super_entities(self):
        """
        Tests the is_type method using one super entity type.
        """
        # Create an account that belongs to a team
        team = Team.objects.create(name='Team')
        account = Account.objects.create(email='test@test.com', team=team)

        # Get the entity related to the account
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        # Check the filter of the super entity type
        self.assertEquals(list(account_entity.get_super_entities().is_any_type(self.team_type)), [team_entity])
        # Check that the filter returns nothing for a different entity type
        self.assertEquals(list(account_entity.get_super_entities().is_any_type(self.account_type)), [])
        # Check that the filter returns the team entity for both types
        self.assertEquals(
            list(account_entity.get_super_entities().is_any_type(self.team_type, self.account_type)), [team_entity])

    def test_is_type_none(self):
        """
        Tests the is_type method using no arguments
        """
        # Create an account that belongs to a team
        team = Team.objects.create(name='Team')
        account = Account.objects.create(email='test@test.com', team=team)

        # Get the entity related to the account
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        self.assertEquals(
            set(account_entity.get_super_entities().is_any_type()), set([team_entity]))

    def test_is_type_sub_entities(self):
        """
        Tests the is_type method on sub entities.
        """
        # Create an account that belongs to a team
        team = Team.objects.create(name='Team')
        account = Account.objects.create(email='test@test.com', team=team)

        # Get the entity related to the account
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        # Check the filter of the sub entity type
        self.assertEquals(list(team_entity.get_sub_entities().is_any_type(self.account_type)), [account_entity])
        # Check that the filter returns nothing for a different entity type
        self.assertEquals(list(team_entity.get_sub_entities().is_any_type(self.team_type)), [])
        # Check that the filter returns the account entity when both types are given
        self.assertEquals(
            list(team_entity.get_sub_entities().is_any_type(self.team_type, self.account_type)), [account_entity])

    def test_is_not_type_super_entities(self):
        """
        Tests the is_not_type method using one super entity type.
        """
        # Create an account that belongs to a team
        team = Team.objects.create(name='Team')
        account = Account.objects.create(email='test@test.com', team=team)

        # Get the entity related to the account
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        # Check the filter of the super entity type
        self.assertEquals(list(account_entity.get_super_entities().is_not_any_type(self.account_type)), [team_entity])
        self.assertEquals(list(account_entity.get_super_entities().is_not_any_type(self.team_type)), [])
        self.assertEquals(
            list(account_entity.get_super_entities().is_not_any_type(self.team_type, self.account_type)), [])

    def test_is_not_type_sub_entities(self):
        """
        Tests the is_not_type method on sub entities.
        """
        # Create an account that belongs to a team
        team = Team.objects.create(name='Team')
        account = Account.objects.create(email='test@test.com', team=team)

        # Get the entity related to the account
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        # Check the filter of the sub entity type
        self.assertEquals(list(team_entity.get_sub_entities().is_not_any_type(self.team_type)), [account_entity])
        self.assertEquals(list(team_entity.get_sub_entities().is_not_any_type(self.account_type)), [])
        self.assertEquals(list(team_entity.get_sub_entities().is_not_any_type(self.team_type, self.account_type)), [])

    def test_return_chained_active_is_any_type(self):
        """
        Tests chaining active and is_type together.
        """
        # Create an account that belongs to a team
        team = Team.objects.create(name='Team')
        account = Account.objects.create(email='test@test.com', team=team)

        # Get the entity related to the account
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        # Check the filter of the sub entity type
        self.assertEquals(
            list(team_entity.get_sub_entities().active().is_any_type(self.account_type)), [account_entity])
