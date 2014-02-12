"""
Provides tests for the syncing functionalities in django entity.
"""
from django.contrib.contenttypes.models import ContentType
from entity.models import Entity, EntityRelationship

from test_project.models import Account, Team, EntityPointer
from .utils import EntityTestCase


class TestAccountEntitySignalSync(EntityTestCase):
    """
    Tests that Account entities (from the test models) are properly synced upon post_save and
    post_delete calls.
    """
    def test_post_delete_no_entity(self):
        """
        Tests a post_delete on an account that has no current mirrored entity.
        """
        # Create an account
        account = Account.objects.create()
        # Clear out the Entity table since post_save will create an entry for it
        Entity.objects.all().delete()

        # Delete the created model. No errors should occur and nothing should
        # be in the entity table
        account.delete()
        self.assertEquals(Entity.objects.all().count(), 0)

    def test_post_delete_account(self):
        """
        Tests a post_delete on an account that has a current mirrored entity.
        """
        # Create accounts for the test
        main_account = Account.objects.create()
        other_account = Account.objects.create()
        # Clear out the Entity table since post_save will create an entry for it
        Entity.objects.all().delete()

        # Create entity entries for the account object and for another account
        self.create_entity(main_account)
        self.create_entity(other_account)

        # Delete the created model. No errors should occur and the other account
        # should still be an entity in the Entity table.
        main_account.delete()
        self.assertEquals(Entity.objects.all().count(), 1)
        self.assertEquals(Entity.objects.filter(entity_id=other_account.id).count(), 1)

    def test_post_delete_account_under_team(self):
        """
        Tests the deletion of an account that had a relationship with a team.
        """
        # Create a team
        team = Team.objects.create(name='Team')
        # Create an account under that team
        account = Account.objects.create(email='test@test.com', team=team)

        # There should be two entities and a relationship between them.
        self.assertEquals(Entity.objects.all().count(), 2)
        self.assertEquals(EntityRelationship.objects.all().count(), 1)

        # Delete the account. The team entity should still exist
        account.delete()
        self.assertEquals(Entity.objects.all().count(), 1)
        self.assertEquals(EntityRelationship.objects.all().count(), 0)
        Entity.objects.get(entity_type=ContentType.objects.get_for_model(team), entity_id=team.id)

    def test_post_create_account_no_relationships_active(self):
        """
        Tests that an Entity is created when the appropriate EntityModelMixin model is
        created. Tests the case where the entity has no relationships.
        """
        # Verify that there are no entities
        self.assertEquals(Entity.objects.all().count(), 0)

        # Create an account. An entity with no relationships should be created
        account = Account.objects.create(email='test@test.com')
        entity = Entity.objects.get(entity_type=ContentType.objects.get_for_model(account), entity_id=account.id)
        # Check that the metadata and is_active fields were set properly
        self.assertEquals(entity.entity_meta, {
            'email': 'test@test.com',
            'is_captain': False,
            'team': None,
        })
        self.assertEquals(entity.is_active, True)

        self.assertEquals(entity.sub_relationships.all().count(), 0)
        self.assertEquals(entity.super_relationships.all().count(), 0)

    def test_post_create_account_relationships(self):
        """
        Creates an account that has super relationships. Verifies that the entity table is updated
        properly.
        """
        # Verify that there are no entities
        self.assertEquals(Entity.objects.all().count(), 0)

        # Create a team
        team = Team.objects.create(name='Team')
        # Create an account under that team
        account = Account.objects.create(email='test@test.com', team=team)

        # There should be two entities. Test their existence and values
        self.assertEquals(Entity.objects.all().count(), 2)
        account_entity = Entity.objects.get(
            entity_type=ContentType.objects.get_for_model(account), entity_id=account.id)
        self.assertEquals(account_entity.entity_meta, {
            'email': 'test@test.com',
            'is_captain': False,
            'team': 'Team',
        })
        team_entity = Entity.objects.get(
            entity_type=ContentType.objects.get_for_model(team), entity_id=team.id)
        self.assertEquals(team_entity.entity_meta, None)

        # Check that the appropriate entity relationship was created
        self.assertEquals(EntityRelationship.objects.all().count(), 1)
        relationship = EntityRelationship.objects.first()
        self.assertEquals(relationship.sub_entity, account_entity)
        self.assertEquals(relationship.super_entity, team_entity)
        self.assertEquals(relationship.is_active, True)

    def test_post_updated_entity_no_cascade(self):
        """
        Verify that updating a mirrored entity does not cause the entity to be deleted (which
        results in a cascading delete for all pointers.
        """
        # Create a test account
        account = Account.objects.create(email='test@test.com')
        entity = Entity.objects.get(entity_type=ContentType.objects.get_for_model(account), entity_id=account.id)
        self.assertEquals(entity.entity_meta, {
            'email': 'test@test.com',
            'is_captain': False,
            'team': None,
        })
        old_entity_id = entity.id

        # Create an object that points to the entity. This object is created to verify that it isn't cascade
        # deleted when the entity is updated
        test_pointer = EntityPointer.objects.create(entity=entity)

        # Now update the account
        account.email = 'newemail@test.com'
        account.save()
        # Verify that the mirrored entity has the same ID
        entity = Entity.objects.get(entity_type=ContentType.objects.get_for_model(account), entity_id=account.id)
        self.assertEquals(entity.entity_meta, {
            'email': 'newemail@test.com',
            'is_captain': False,
            'team': None,
        })
        self.assertEquals(old_entity_id, entity.id)

        # Verify that the pointer still exists and wasn't cascade deleted
        test_pointer = EntityPointer.objects.get(id=test_pointer.id)
        self.assertEquals(test_pointer.entity, entity)

    def test_post_update_account_meta(self):
        """
        Verifies that an account's metadata is updated properly in the mirrored tables.
        """
        # Create an account and check it's mirrored metadata
        account = Account.objects.create(email='test@test.com')
        entity = Entity.objects.get(entity_type=ContentType.objects.get_for_model(account), entity_id=account.id)
        self.assertEquals(entity.entity_meta, {
            'email': 'test@test.com',
            'is_captain': False,
            'team': None,
        })

        # Update the account's metadata and check that it is mirrored
        account.email = 'newemail@test.com'
        account.save()
        entity = Entity.objects.get(entity_type=ContentType.objects.get_for_model(account), entity_id=account.id)
        self.assertEquals(entity.entity_meta, {
            'email': 'newemail@test.com',
            'is_captain': False,
            'team': None,
        })

    def test_post_update_account_relationship_activity(self):
        """
        Creates an account that has super relationships. Verifies that the entity table is updated
        properly when changing the activity of a relationship.
        """
        # Verify that there are no entities
        self.assertEquals(Entity.objects.all().count(), 0)

        # Create a team
        team = Team.objects.create(name='Team')
        # Create an account under that team
        account = Account.objects.create(email='test@test.com', team=team)

        # There should be two entities. Test their existence and values
        self.assertEquals(Entity.objects.all().count(), 2)
        account_entity = Entity.objects.get(
            entity_type=ContentType.objects.get_for_model(account), entity_id=account.id)
        self.assertEquals(account_entity.entity_meta, {
            'email': 'test@test.com',
            'is_captain': False,
            'team': 'Team',
        })
        team_entity = Entity.objects.get(
            entity_type=ContentType.objects.get_for_model(team), entity_id=team.id)
        self.assertEquals(team_entity.entity_meta, None)

        # Check that the appropriate entity relationship was created
        self.assertEquals(EntityRelationship.objects.all().count(), 1)
        relationship = EntityRelationship.objects.first()
        self.assertEquals(relationship.sub_entity, account_entity)
        self.assertEquals(relationship.super_entity, team_entity)
        self.assertEquals(relationship.is_active, True)

        # Update the account to be a team captain. According to our test project, this
        # means it no longer has an active relationship to a team
        account.is_captain = True
        account.save()

        # Verify that it no longer has an active relationship
        self.assertEquals(EntityRelationship.objects.all().count(), 1)
        relationship = EntityRelationship.objects.first()
        self.assertEquals(relationship.sub_entity, account_entity)
        self.assertEquals(relationship.super_entity, team_entity)
        self.assertEquals(relationship.is_active, False)
