"""
Provides tests for the syncing functionalities in django entity.
"""
from mock import patch

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db.models.signals import post_delete, post_save
from django.test.utils import override_settings
from entity.models import Entity, EntityRelationship, delete_entity_signal_handler, save_entity_signal_handler
from entity.sync import sync_entities, turn_on_syncing, turn_off_syncing

from .models import Account, Team, EntityPointer, DummyModel, MultiInheritEntity
from .utils import EntityTestCase


class TestTurnOnOffSyncing(EntityTestCase):
    """
    Tests turning on and off entity syncing.
    """
    def tearDown(self):
        super(TestTurnOnOffSyncing, self).tearDown()
        # Make sure syncing is always on before every test
        turn_on_syncing()

    def test_post_save_turned_on_by_default(self):
        """
        Tests that save signals are connected by default.
        """
        with patch('entity.models.sync_entity_signal_handler') as mock_handler:
            Account.objects.create()
            self.assertTrue(mock_handler.called)

    def test_post_delete_turned_on_by_default(self):
        """
        Tests that delete signals are connected by default.
        """
        with patch('entity.models.sync_entity_signal_handler') as mock_handler:
            a = Account.objects.create()
            self.assertEquals(mock_handler.call_count, 1)

            # Delete the object. The signal should be called
            a.delete()
            self.assertEquals(mock_handler.call_count, 2)

    def test_bulk_operation_turned_on_by_default(self):
        """
        Tests that bulk operations are turned on by default.
        """
        with patch('entity.models.sync_entities_signal_handler') as mock_handler:
            Account.objects.bulk_create([Account() for i in range(5)])
            self.assertTrue(mock_handler.called)

    def test_turn_off_save(self):
        """
        Tests turning off syncing for the save signal.
        """
        turn_off_syncing()
        with patch('entity.models.sync_entity_signal_handler') as mock_handler:
            Account.objects.create()
            self.assertFalse(mock_handler.called)

    def test_turn_off_delete(self):
        """
        Tests turning off syncing for the delete signal.
        """
        turn_off_syncing()
        with patch('entity.models.sync_entity_signal_handler') as mock_handler:
            a = Account.objects.create()
            self.assertFalse(mock_handler.called)
            a.delete()
            self.assertFalse(mock_handler.called)

    def test_turn_off_bulk(self):
        """
        Tests turning off syncing for bulk operations.
        """
        turn_off_syncing()
        with patch('entity.models.sync_entities_signal_handler') as mock_handler:
            Account.objects.bulk_create([Account() for i in range(5)])
            self.assertFalse(mock_handler.called)

    def test_turn_on_save(self):
        """
        Tests turning on syncing for the save signal.
        """
        turn_off_syncing()
        turn_on_syncing()
        with patch('entity.models.sync_entity_signal_handler') as mock_handler:
            Account.objects.create()
            self.assertTrue(mock_handler.called)

    def test_turn_on_delete(self):
        """
        Tests turning on syncing for the delete signal.
        """
        turn_off_syncing()
        turn_on_syncing()
        with patch('entity.models.sync_entity_signal_handler') as mock_handler:
            a = Account.objects.create()
            self.assertEquals(mock_handler.call_count, 1)
            a.delete()
            self.assertEquals(mock_handler.call_count, 2)

    def test_turn_on_bulk(self):
        """
        Tests turning on syncing for bulk operations.
        """
        turn_off_syncing()
        turn_on_syncing()
        with patch('entity.models.sync_entities_signal_handler') as mock_handler:
            Account.objects.bulk_create([Account() for i in range(5)])
            self.assertTrue(mock_handler.called)


class TestSyncAllEntities(EntityTestCase):
    """
    Tests that all entities can be synced at once and tests the management command to
    sync all entities.
    """
    def setUp(self):
        super(TestSyncAllEntities, self).setUp()
        # Disconnect signal handlers to test syncing all entities
        post_delete.disconnect(delete_entity_signal_handler, dispatch_uid='delete_entity_signal_handler')
        post_save.disconnect(save_entity_signal_handler, dispatch_uid='save_entity_signal_handler')

    def tearDown(self):
        super(TestSyncAllEntities, self).tearDown()
        # Reconnect signal handlers
        post_delete.connect(delete_entity_signal_handler, dispatch_uid='delete_entity_signal_handler')
        post_save.connect(save_entity_signal_handler, dispatch_uid='save_entity_signal_handler')

    def test_sync_entities_management_command(self):
        """
        Tests that the management command for syncing entities works properly.
        """
        # Create five test accounts
        for i in range(5):
            Account.objects.create()

        # Test that the management command syncs all five entities
        self.assertEquals(Entity.objects.all().count(), 0)
        call_command('sync_entities')
        self.assertEquals(Entity.objects.all().count(), 5)

    @override_settings(CELERY_EAGER_PROPAGATES_EXCEPTIONS=True, CELERY_ALWAYS_EAGER=True, BROKER_BACKEND='memory')
    def test_async_sync_entities_management_command(self):
        """
        Tests that the sync_entities command works with the asynchronous option.
        """
        # Create five test accounts
        for i in range(5):
            Account.objects.create()

        # Test that the management command syncs all five entities
        self.assertEquals(Entity.objects.all().count(), 0)
        call_command('sync_entities', async=True)
        self.assertEquals(Entity.objects.all().count(), 5)

    def test_sync_dummy_data(self):
        """
        Tests that dummy data (i.e data that does not inherit EntityModelMixin) doesn't
        get synced.
        """
        # Create dummy data
        DummyModel.objects.create()
        # Sync all entities and verify that none were created
        sync_entities()
        self.assertEquals(Entity.objects.all().count(), 0)

    def test_sync_multi_inherited_data(self):
        """
        Test when models are synced that don't directly inherit EntityModelMixin.
        """
        # Create an entity that does not directly inherit EntityModelMixin
        MultiInheritEntity.objects.create()
        # Sync all entities and verify that one was created
        sync_entities()
        self.assertEquals(Entity.objects.all().count(), 1)

    def test_sync_all_account_no_teams(self):
        """
        Tests syncing all accounts with no super entities.
        """
        # Create five test accounts
        accounts = [Account.objects.create() for i in range(5)]

        # Sync all of the entities and verify that five Entity models were created for the Account model
        self.assertEquals(Entity.objects.all().count(), 0)
        sync_entities()
        self.assertEquals(Entity.objects.all().count(), 5)

        # Delete an account. When all entities are synced again,
        # there should only be four accounts
        accounts[0].delete()
        self.assertEquals(Entity.objects.all().count(), 5)
        sync_entities()
        self.assertEquals(Entity.objects.all().count(), 4)

    def test_sync_all_accounts_teams(self):
        """
        Tests syncing of all accounts when they have syper entities.
        """
        # Create five test accounts
        accounts = [Account.objects.create() for i in range(5)]
        # Create two teams to assign to some of the accounts
        teams = [Team.objects.create() for i in range(2)]
        accounts[0].team = teams[0]
        accounts[0].save()
        accounts[1].team = teams[0]
        accounts[1].save()
        accounts[2].team = teams[1]
        accounts[2].save()
        accounts[3].team = teams[1]
        accounts[3].save()

        # Sync all the entities. There should be 7 (5 accounts 2 teams)
        sync_entities()
        self.assertEquals(Entity.objects.filter(entity_type=ContentType.objects.get_for_model(Account)).count(), 5)
        self.assertEquals(Entity.objects.filter(entity_type=ContentType.objects.get_for_model(Team)).count(), 2)
        self.assertEquals(Entity.objects.all().count(), 7)

        # There should be four entity relationships since four accounts have teams
        self.assertEquals(EntityRelationship.objects.all().count(), 4)

    def test_sync_optimal_queries(self):
        """
        Tests optimal queries of syncing.
        """
        # Create five test accounts
        accounts = [Account.objects.create() for i in range(5)]
        # Create two teams to assign to some of the accounts
        teams = [Team.objects.create() for i in range(2)]
        accounts[0].team = teams[0]
        accounts[0].save()
        accounts[1].team = teams[0]
        accounts[1].save()
        accounts[2].team = teams[1]
        accounts[2].save()
        accounts[3].team = teams[1]
        accounts[3].save()

        with self.assertNumQueries(56):
            sync_entities()


class TestEntitySignalSync(EntityTestCase):
    """
    Tests that entities (from the test models) are properly synced upon post_save and
    post_delete calls.
    """
    def test_post_bulk_create(self):
        """
        Tests that entities can have bulk creates applied to them and still be synced.
        """
        # Bulk create five accounts
        accounts = [Account() for i in range(5)]
        Account.objects.bulk_create(accounts)
        # Verify that there are 5 entities
        self.assertEquals(Entity.objects.all().count(), 5)

    def test_post_bulk_update(self):
        """
        Calls a bulk update on a list of entities. Verifies that the models are appropriately
        synced.
        """
        # Create five accounts
        for i in range(5):
            Account.objects.create(email='test1@test.com')
        # Verify that there are five entities all with the 'test1@test.com' email
        for entity in Entity.objects.all():
            self.assertEquals(entity.entity_meta['email'], 'test1@test.com')
        self.assertEquals(Entity.objects.all().count(), 5)

        # Bulk update the account emails to a different one
        Account.objects.all().update(email='test2@test.com')

        # Verify that the email was updated properly in all entities
        for entity in Entity.objects.all():
            self.assertEquals(entity.entity_meta['email'], 'test2@test.com')
        self.assertEquals(Entity.objects.all().count(), 5)

    def test_post_bulk_update_dummy(self):
        """
        Tests that even if the dummy model is using the special model manager for bulk
        updates, it still does not get synced since it doesn't inherit EntityModelMixin.
        """
        # Create five dummy models with a bulk update
        DummyModel.objects.bulk_create([DummyModel() for i in range(5)])
        # There should be no synced entities
        self.assertEquals(Entity.objects.all().count(), 0)

    def test_post_save_dummy_data(self):
        """
        Tests that dummy data that does not inherit from EntityModelMixin is not synced
        when saved.
        """
        DummyModel.objects.create()
        # Verify that no entities were created
        self.assertEquals(Entity.objects.all().count(), 0)

    def test_post_save_multi_inherit_model(self):
        """
        Tests that a model that does not directly inherit EntityModelMixin is still synced.
        """
        MultiInheritEntity.objects.create()
        # Verify that one entity was synced
        self.assertEquals(Entity.objects.all().count(), 1)

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
        Entity.objects.get_for_obj(team)

    def test_post_create_account_no_relationships_active(self):
        """
        Tests that an Entity is created when the appropriate EntityModelMixin model is
        created. Tests the case where the entity has no relationships.
        """
        # Verify that there are no entities
        self.assertEquals(Entity.objects.all().count(), 0)

        # Create an account. An entity with no relationships should be created
        account = Account.objects.create(email='test@test.com')
        entity = Entity.objects.get_for_obj(account)
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
        account_entity = Entity.objects.get_for_obj(account)
        self.assertEquals(account_entity.entity_meta, {
            'email': 'test@test.com',
            'is_captain': False,
            'team': 'Team',
        })
        team_entity = Entity.objects.get_for_obj(team)
        self.assertEquals(team_entity.entity_meta, None)

        # Check that the appropriate entity relationship was created
        self.assertEquals(EntityRelationship.objects.all().count(), 1)
        relationship = EntityRelationship.objects.first()
        self.assertEquals(relationship.sub_entity, account_entity)
        self.assertEquals(relationship.super_entity, team_entity)

    def test_post_updated_entity_no_cascade(self):
        """
        Verify that updating a mirrored entity does not cause the entity to be deleted (which
        results in a cascading delete for all pointers.
        """
        # Create a test account
        account = Account.objects.create(email='test@test.com')
        entity = Entity.objects.get_for_obj(account)
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
        entity = Entity.objects.get_for_obj(account)
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
        entity = Entity.objects.get_for_obj(account)
        self.assertEquals(entity.entity_meta, {
            'email': 'test@test.com',
            'is_captain': False,
            'team': None,
        })

        # Update the account's metadata and check that it is mirrored
        account.email = 'newemail@test.com'
        account.save()
        entity = Entity.objects.get_for_obj(account)
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
        account_entity = Entity.objects.get_for_obj(account)
        self.assertEquals(account_entity.entity_meta, {
            'email': 'test@test.com',
            'is_captain': False,
            'team': 'Team',
        })
        team_entity = Entity.objects.get_for_obj(team)
        self.assertEquals(team_entity.entity_meta, None)

        # Check that the appropriate entity relationship was created
        self.assertEquals(EntityRelationship.objects.all().count(), 1)
        relationship = EntityRelationship.objects.first()
        self.assertEquals(relationship.sub_entity, account_entity)
        self.assertEquals(relationship.super_entity, team_entity)

        # Update the account to be a team captain. According to our test project, this
        # means it no longer has an active relationship to a team
        account.is_captain = True
        account.save()

        # Verify that it no longer has an active relationship
        self.assertEquals(EntityRelationship.objects.all().count(), 1)
        relationship = EntityRelationship.objects.first()
        self.assertEquals(relationship.sub_entity, account_entity)
        self.assertEquals(relationship.super_entity, team_entity)
