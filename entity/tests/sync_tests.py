"""
Provides tests for the syncing functionalities in django entity.
"""
from django import db
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django_dynamic_fixture import G
from entity.config import EntityRegistry
from entity.models import Entity, EntityRelationship, EntityKind
from entity.sync import (
    sync_entities, defer_entity_syncing, transaction_atomic_with_retry, _get_super_entities_by_ctype,
    suppress_entity_syncing,
)
from entity.signal_handlers import turn_on_syncing, turn_off_syncing
from mock import patch, MagicMock, call

from entity.tests.models import (
    Account, Team, EntityPointer, DummyModel, MultiInheritEntity, AccountConfig, TeamConfig, TeamGroup,
    M2mEntity, PointsToM2mEntity, PointsToAccount, Competitor
)
from entity.tests.utils import EntityTestCase


class TestTurnOnOffSyncing(EntityTestCase):
    """
    Tests turning on and off entity syncing.
    """
    @patch('entity.signal_handlers.post_save', spec_set=True)
    @patch('entity.signal_handlers.post_delete', spec_set=True)
    @patch('entity.signal_handlers.m2m_changed', spec_set=True)
    @patch('entity.signal_handlers.post_bulk_operation', spec_set=True)
    def test_turn_on_syncing_all_handlers_true(
            self, post_bulk_operation_mock, m2m_changed_mock, post_delete_mock, post_save_mock):
        turn_on_syncing(for_post_save=True, for_post_delete=True, for_m2m_changed=True, for_post_bulk_operation=True)
        self.assertTrue(post_save_mock.connect.called)
        self.assertTrue(post_delete_mock.connect.called)
        self.assertTrue(m2m_changed_mock.connect.called)
        self.assertTrue(post_bulk_operation_mock.connect.called)

    @patch('entity.signal_handlers.post_save', spec_set=True)
    @patch('entity.signal_handlers.post_delete', spec_set=True)
    @patch('entity.signal_handlers.m2m_changed', spec_set=True)
    @patch('entity.signal_handlers.post_bulk_operation', spec_set=True)
    def test_turn_on_syncing_all_handlers_false(
            self, post_bulk_operation_mock, m2m_changed_mock, post_delete_mock, post_save_mock):
        turn_on_syncing(
            for_post_save=False, for_post_delete=False, for_m2m_changed=False, for_post_bulk_operation=False)
        self.assertFalse(post_save_mock.connect.called)
        self.assertFalse(post_delete_mock.connect.called)
        self.assertFalse(m2m_changed_mock.connect.called)
        self.assertFalse(post_bulk_operation_mock.connect.called)

    @patch('entity.signal_handlers.post_save', spec_set=True)
    @patch('entity.signal_handlers.post_delete', spec_set=True)
    @patch('entity.signal_handlers.m2m_changed', spec_set=True)
    @patch('entity.signal_handlers.post_bulk_operation', spec_set=True)
    def test_turn_off_syncing_all_handlers_true(
            self, post_bulk_operation_mock, m2m_changed_mock, post_delete_mock, post_save_mock):
        turn_off_syncing(for_post_save=True, for_post_delete=True, for_m2m_changed=True, for_post_bulk_operation=True)
        self.assertTrue(post_save_mock.disconnect.called)
        self.assertTrue(post_delete_mock.disconnect.called)
        self.assertTrue(m2m_changed_mock.disconnect.called)
        self.assertTrue(post_bulk_operation_mock.disconnect.called)

    @patch('entity.signal_handlers.post_save', spec_set=True)
    @patch('entity.signal_handlers.post_delete', spec_set=True)
    @patch('entity.signal_handlers.m2m_changed', spec_set=True)
    @patch('entity.signal_handlers.post_bulk_operation', spec_set=True)
    def test_turn_off_syncing_all_handlers_false(
            self, post_bulk_operation_mock, m2m_changed_mock, post_delete_mock, post_save_mock):
        turn_off_syncing(
            for_post_save=False, for_post_delete=False, for_m2m_changed=False, for_post_bulk_operation=False)
        self.assertFalse(post_save_mock.disconnect.called)
        self.assertFalse(post_delete_mock.disconnect.called)
        self.assertFalse(m2m_changed_mock.disconnect.called)
        self.assertFalse(post_bulk_operation_mock.disconnect.called)

    def test_post_save_turned_on_by_default(self):
        """
        Tests that save signals are connected by default.
        """
        with patch('entity.signal_handlers.sync_entities') as mock_handler:
            Account.objects.create()
            self.assertTrue(mock_handler.called)

    def test_post_delete_turned_on_by_default(self):
        """
        Tests that delete signals are connected by default.
        """
        a = Account.objects.create()
        with patch('entity.models.Entity.all_objects.delete_for_obj') as mock_handler:
            # Delete the object. The signal should be called
            a.delete()
            self.assertEquals(mock_handler.call_count, 1)

    def test_bulk_operation_turned_off_by_default(self):
        """
        Tests that bulk operations are turned off by default.
        """
        with patch('entity.signal_handlers.sync_entities') as mock_handler:
            Account.objects.bulk_create([Account() for i in range(5)])
            self.assertFalse(mock_handler.called)

    def test_turn_off_save(self):
        """
        Tests turning off syncing for the save signal.
        """
        turn_off_syncing()
        with patch('entity.signal_handlers.sync_entities') as mock_handler:
            Account.objects.create()
            self.assertFalse(mock_handler.called)

    def test_turn_off_delete(self):
        """
        Tests turning off syncing for the delete signal.
        """
        turn_off_syncing()
        with patch('entity.signal_handlers.sync_entities') as mock_handler:
            a = Account.objects.create()
            self.assertFalse(mock_handler.called)
            a.delete()
            self.assertFalse(mock_handler.called)

    def test_turn_off_bulk(self):
        """
        Tests turning off syncing for bulk operations.
        """
        turn_off_syncing()
        with patch('entity.signal_handlers.sync_entities') as mock_handler:
            Account.objects.bulk_create([Account() for i in range(5)])
            self.assertFalse(mock_handler.called)

    def test_turn_on_save(self):
        """
        Tests turning on syncing for the save signal.
        """
        turn_off_syncing()
        turn_on_syncing()
        with patch('entity.signal_handlers.sync_entities') as mock_handler:
            Account.objects.create()
            self.assertTrue(mock_handler.called)

    def test_turn_on_delete(self):
        """
        Tests turning on syncing for the delete signal.
        """
        turn_off_syncing()
        turn_on_syncing()
        with patch('entity.models.Entity.all_objects.delete_for_obj') as mock_handler:
            a = Account.objects.create()
            a.delete()
            self.assertEquals(mock_handler.call_count, 1)

    def test_turn_on_bulk(self):
        """
        Tests turning on syncing for bulk operations.
        """
        turn_off_syncing()
        turn_on_syncing(for_post_bulk_operation=True)
        with patch('entity.signal_handlers.sync_entities') as mock_handler:
            Account.objects.bulk_create([Account() for i in range(5)])
            self.assertTrue(mock_handler.called)


class SyncAllEntitiesTest(EntityTestCase):
    """
    Tests that all entities can be synced at once and tests the management command to
    sync all entities.
    """
    def test_sync_entities_management_command(self):
        """
        Tests that the management command for syncing entities works properly.
        """
        # Create five test accounts
        turn_off_syncing()
        for i in range(5):
            Account.objects.create()
        turn_on_syncing()

        # Test that the management command syncs all five entities
        self.assertEquals(Entity.objects.all().count(), 0)
        call_command('sync_entities')
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
        turn_off_syncing()
        # Create five test accounts
        accounts = [Account.objects.create() for i in range(5)]
        turn_on_syncing()

        # Sync all of the entities and verify that five Entity models were created for the Account model
        self.assertEquals(Entity.objects.all().count(), 0)
        sync_entities()
        self.assertEquals(Entity.objects.all().count(), 5)

        # Delete an account. When all entities are synced again,
        # there should only be four accounts
        turn_off_syncing()
        accounts[0].delete()
        turn_on_syncing()

        self.assertEquals(Entity.objects.all().count(), 5)
        sync_entities()
        self.assertEquals(Entity.objects.all().count(), 4)

    def test_sync_all_accounts_teams(self):
        """
        Tests syncing of all accounts when they have super entities.
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

    def test_sync_all_accounts_teams_new_account_during_sync(self):
        """
        Tests the scenario of a new account being created after account ids are fetched but before the super
        entities are fetched
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

        def wrapped_super_entities(*args, **kwargs):
            if not Account.objects.filter(email='fake@fake.com').exists():
                Account.objects.create(
                    email='fake@fake.com',
                    team=Team.objects.order_by('id')[0],
                    team2=Team.objects.order_by('id')[1],
                )

            return _get_super_entities_by_ctype(*args, **kwargs)

        # Sync all the entities. There should be 8 (6 accounts 2 teams)
        with patch('entity.sync._get_super_entities_by_ctype', wraps=wrapped_super_entities):
            sync_entities()

        self.assertEquals(Entity.objects.filter(entity_type=ContentType.objects.get_for_model(Account)).count(), 6)
        self.assertEquals(Entity.objects.filter(entity_type=ContentType.objects.get_for_model(Team)).count(), 2)
        self.assertEquals(Entity.objects.all().count(), 8)

        # There should be six entity relationships
        self.assertEquals(EntityRelationship.objects.all().count(), 6)

    def test_sync_all_accounts_teams_deleted_account_during_sync(self):
        """
        Tests the scenario of an account being deleted after account ids are fetched but before the super
        entities are fetched
        """
        # Create five test accounts
        accounts = [Account.objects.create() for i in range(5)]
        # Create two teams to assign to some of the accounts
        teams = [Team.objects.create() for i in range(2)]
        accounts[0].team = teams[0]
        accounts[0].email = 'fake@fake.com'
        accounts[0].save()
        accounts[1].team = teams[0]
        accounts[1].save()
        accounts[2].team = teams[1]
        accounts[2].save()
        accounts[3].team = teams[1]
        accounts[3].save()

        def wrapped_super_entities(*args, **kwargs):
            account = Account.objects.filter(email='fake@fake.com', is_active=True).first()
            if account:
                account.is_active = False
                account.save()

            return _get_super_entities_by_ctype(*args, **kwargs)

        # Sync the accounts
        with patch('entity.sync._get_super_entities_by_ctype', wraps=wrapped_super_entities):
            sync_entities(*accounts)
            account = Account.objects.get(email='fake@fake.com')
            entity = Entity.all_objects.get_for_obj(account)
            self.assertEqual(entity.is_active, False)

        # Fetch accounts and sync again - hits other block in wrapped function
        with patch('entity.sync._get_super_entities_by_ctype', wraps=wrapped_super_entities):
            accounts = Account.objects.all()
            sync_entities(*accounts)
            account = Account.objects.get(email='fake@fake.com')
            entity = Entity.all_objects.get_for_obj(account)
            self.assertEqual(entity.is_active, False)

        self.assertEquals(Entity.objects.filter(entity_type=ContentType.objects.get_for_model(Account)).count(), 4)
        self.assertEquals(Entity.objects.filter(entity_type=ContentType.objects.get_for_model(Team)).count(), 2)
        self.assertEquals(Entity.objects.all().count(), 6)

        # There should be six entity relationships
        self.assertEquals(EntityRelationship.objects.all().count(), 4)

    def test_sync_all_accounts_teams_inactive_entity_kind(self):
        """
        Tests syncing of all accounts when they have super entities and the entity kind is inactive
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

        team_ek = EntityKind.objects.get(name='tests.team')
        team_ek.delete()

        # Sync all the entities. There should be 7 (5 accounts 2 teams)
        sync_entities()
        self.assertEquals(Entity.objects.filter(entity_type=ContentType.objects.get_for_model(Account)).count(), 5)
        self.assertEquals(Entity.objects.filter(entity_type=ContentType.objects.get_for_model(Team)).count(), 2)
        self.assertEquals(Entity.objects.all().count(), 7)

        # There should be four entity relationships since four accounts have teams
        self.assertEquals(EntityRelationship.objects.all().count(), 4)


class SyncSignalTests(EntityTestCase):
    """
    Test that when we are syncing we are calling the proper signals
    """

    @patch('entity.sync.model_activations_changed')
    def test_sync_all(self, mock_model_activations_changed):
        """
        Tests that when we sync all we fire the correct signals
        """

        # Create five test accounts
        turn_off_syncing()
        initial_accounts = []
        for i in range(5):
            initial_accounts.append(Account.objects.create())
        turn_on_syncing()

        # Test that the management command syncs all five entities
        self.assertEquals(Entity.objects.all().count(), 0)
        sync_entities()
        self.assertEquals(Entity.objects.all().count(), 5)
        initial_entity_ids = list(Entity.objects.all().values_list('id', flat=True))
        mock_model_activations_changed.send.assert_called_once_with(
            sender=Entity,
            instance_ids=sorted(initial_entity_ids),
            is_active=True
        )

        # Create five new test accounts, and deactivate our initial accounts
        mock_model_activations_changed.reset_mock()
        turn_off_syncing()
        new_accounts = []
        for i in range(5):
            new_accounts.append(Account.objects.create())
        for account in initial_accounts:
            account.delete()
        turn_on_syncing()

        # Sync entities
        sync_entities()

        # Assert that the correct signals were called
        self.assertEqual(
            mock_model_activations_changed.send.mock_calls,
            [
                call(
                    sender=Entity,
                    instance_ids=sorted(list(Entity.objects.filter(
                        entity_id__in=[account.id for account in new_accounts]
                    ).values_list('id', flat=True))),
                    is_active=True
                ),
                call(
                    sender=Entity,
                    instance_ids=sorted(initial_entity_ids),
                    is_active=False
                )
            ]
        )

        # Test syncing all when nothing should have changed
        mock_model_activations_changed.reset_mock()
        sync_entities()
        self.assertFalse(mock_model_activations_changed.send.called)


class TestEntityBulkSignalSync(EntityTestCase):
    """
    Tests syncing when bulk operations happen.
    """
    def setUp(self):
        super(TestEntityBulkSignalSync, self).setUp()
        turn_on_syncing(for_post_bulk_operation=True)

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

    def test_invalid_entity_model(self):
        """
        Tests that an invalid entity model is not synced on bulk update.
        """
        DummyModel.objects.bulk_create([DummyModel()])
        self.assertFalse(Entity.objects.exists())

    def test_post_bulk_update_dummy(self):
        """
        Tests that even if the dummy model is using the special model manager for bulk
        updates, it still does not get synced since it doesn't inherit EntityModelMixin.
        """
        # Create five dummy models with a bulk update
        DummyModel.objects.bulk_create([DummyModel() for i in range(5)])
        # There should be no synced entities
        self.assertEquals(Entity.objects.all().count(), 0)


class TestWatching(EntityTestCase):
    """
    Tests when an entity is watching another model for changes.
    """
    def test_m2m_changed_of_another_model(self):
        """
        Tests when an entity model is listening for a change of an m2m of another model.
        """
        m2m_entity = G(M2mEntity)
        team = G(Team)
        points_to_m2m_entity = G(PointsToM2mEntity, m2m_entity=m2m_entity)
        # Three entities should be synced and there should not yet be any relationships
        self.assertEquals(Entity.objects.count(), 3)
        self.assertFalse(EntityRelationship.objects.exists())

        # When a team is added to the m2m entity, it should be a super entity to the points_to_m2m_entity and
        # of m2m_entity
        m2m_entity.teams.add(team)
        self.assertEquals(Entity.objects.count(), 3)
        self.assertEquals(EntityRelationship.objects.count(), 2)

        points_to_m2m_entity = Entity.objects.get_for_obj(points_to_m2m_entity)
        team_entity = Entity.objects.get_for_obj(team)
        m2m_entity = Entity.objects.get_for_obj(m2m_entity)
        self.assertTrue(EntityRelationship.objects.filter(
            sub_entity=points_to_m2m_entity, super_entity=team_entity).exists())
        self.assertTrue(EntityRelationship.objects.filter(sub_entity=m2m_entity, super_entity=team_entity).exists())

    def test_points_to_account_config_competitor_updated(self):
        """
        Tests that a PointsToAccount model is updated when the competitor of its account is updated.
        """
        account = G(Account)
        pta = G(PointsToAccount, account=account)
        pta_entity = Entity.objects.get_for_obj(pta)
        self.assertEquals(pta_entity.entity_meta, {
            'team_name': 'None',
            'competitor_name': 'None',
        })

        team = G(Team, name='team1')
        competitor = G(Competitor, name='competitor1')
        account.team = team
        account.competitor = competitor
        account.save()

        # Nothing should have been updated on the entity. This is because it is watching the competitor
        # and team models for changes. Since these models were changed before they were linked to the
        # account, the changes are not propagated.
        pta_entity = Entity.objects.get_for_obj(pta)
        self.assertEquals(pta_entity.entity_meta, {
            'team_name': 'None',
            'competitor_name': 'None',
        })

        # Now change names of the competitors and teams. Things will be propagated.
        team.name = 'team2'
        team.save()
        pta_entity = Entity.objects.get_for_obj(pta)
        self.assertEquals(pta_entity.entity_meta, {
            'team_name': 'team2',
            'competitor_name': 'competitor1',
        })

        competitor.name = 'competitor2'
        competitor.save()
        pta_entity = Entity.objects.get_for_obj(pta)
        self.assertEquals(pta_entity.entity_meta, {
            'team_name': 'team2',
            'competitor_name': 'competitor2',
        })

        # The power of django entity compels you...


class TestEntityM2mChangedSignalSync(EntityTestCase):
    """
    Tests when an m2m changes on a synced entity.
    """
    def test_save_model_with_m2m(self):
        """
        Verifies that the m2m test entity is synced properly upon save.
        """
        turn_off_syncing()
        m = G(M2mEntity)
        m.teams.add(G(Team))
        turn_on_syncing()

        m.save()
        self.assertEquals(Entity.objects.count(), 2)
        self.assertEquals(EntityRelationship.objects.count(), 1)

    def test_sync_when_m2m_add(self):
        """
        Verifies an entity is synced properly when and m2m field is added.
        """
        m = G(M2mEntity)
        self.assertEquals(Entity.objects.count(), 1)
        self.assertEquals(EntityRelationship.objects.count(), 0)
        m.teams.add(G(Team))
        self.assertEquals(Entity.objects.count(), 2)
        self.assertEquals(EntityRelationship.objects.count(), 1)

    def test_sync_when_m2m_delete(self):
        """
        Verifies an entity is synced properly when and m2m field is deleted.
        """
        m = G(M2mEntity)
        team = G(Team)
        m.teams.add(team)
        self.assertEquals(Entity.objects.count(), 2)
        self.assertEquals(EntityRelationship.objects.count(), 1)
        m.teams.remove(team)
        self.assertEquals(Entity.objects.count(), 2)
        self.assertEquals(EntityRelationship.objects.count(), 0)

    def test_sync_when_m2m_clear(self):
        """
        Verifies an entity is synced properly when and m2m field is cleared.
        """
        m = G(M2mEntity)
        team = G(Team)
        m.teams.add(team)
        self.assertEquals(Entity.objects.count(), 2)
        self.assertEquals(EntityRelationship.objects.count(), 1)
        m.teams.clear()
        self.assertEquals(Entity.objects.count(), 2)
        self.assertEquals(EntityRelationship.objects.count(), 0)


class TestEntityPostSavePostDeleteSignalSync(EntityTestCase):
    """
    Tests that entities (from the test models) are properly synced upon post_save
    and post_delete signals.
    """
    def test_going_from_inactive_to_active(self):
        """
        Tests that an inactive entity can be activated and that its active attributes
        are synced properly.
        """
        a = Account.objects.create(email='test_email', is_active=False)
        a.is_active = True
        a.save()
        e = Entity.all_objects.get_for_obj(a)
        self.assertTrue(e.is_active)

    def test_inactive_syncing(self):
        """
        Tests that an inactive entity's activatable properties are synced properly.
        """
        a = Account.objects.create(email='test_email', is_active=False)
        e = Entity.all_objects.get_for_obj(a)
        self.assertFalse(e.is_active)

    def test_display_name_mirrored_default(self):
        """
        Tests that the display name is mirrored to the __unicode__ of the models. This
        is the default behavior.
        """
        a = Account.objects.create(email='test_email')
        e = Entity.objects.get_for_obj(a)
        self.assertEquals(e.display_name, 'test_email')

    def test_display_name_mirrored_custom(self):
        """
        Tests that the display name is mirrored properly when a custom get_display_name
        function is defined. In this case, the function for Teams returns 'team'
        """
        t = G(Team)
        e = Entity.objects.get_for_obj(t)
        self.assertEquals(e.display_name, 'team')

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

    def test_post_delete_inactive_entity(self):
        """
        Tests deleting an entity that was already inactive.
        """
        account = Account.objects.create(is_active=False)
        account.delete()
        self.assertEquals(Entity.all_objects.all().count(), 0)

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
        Entity.objects.all().delete(force=True)

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
            'team_is_active': None,
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
            'team_is_active': True,
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
            'team_is_active': None,
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
            'team_is_active': None,
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
            'team_is_active': None,
        })

        # Update the account's metadata and check that it is mirrored
        account.email = 'newemail@test.com'
        account.save()
        entity = Entity.objects.get_for_obj(account)
        self.assertEquals(entity.entity_meta, {
            'email': 'newemail@test.com',
            'is_captain': False,
            'team': None,
            'team_is_active': None,
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
            'team_is_active': True,
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


class TestSyncingMultipleEntities(EntityTestCase):
    """
    Tests syncing multiple entities at once of different types.
    """
    def test_sync_two_accounts(self):
        turn_off_syncing()
        team = G(Team)
        account1 = G(Account, team=team)
        account2 = G(Account, team=team)
        G(TeamGroup)
        sync_entities(account1, account2)

        self.assertEquals(Entity.objects.count(), 3)
        self.assertEquals(EntityRelationship.objects.count(), 2)

    def test_sync_two_accounts_one_team_group(self):
        turn_off_syncing()
        team = G(Team)
        account1 = G(Account, team=team)
        account2 = G(Account, team=team)
        team_group = G(TeamGroup)
        sync_entities(account1, account2, team_group)

        self.assertEquals(Entity.objects.count(), 4)
        self.assertEquals(EntityRelationship.objects.count(), 2)


class TestCachingAndCascading(EntityTestCase):
    """
    Tests caching, cascade syncing, and optimal queries when syncing single, multiple, or all entities.
    """
    def test_cascade_sync_super_entities(self):
        """
        Tests that super entities will be synced when a sub entity is synced (even if the super entities
        werent synced before)
        """
        turn_off_syncing()
        team = G(Team)
        turn_on_syncing()

        self.assertFalse(Entity.objects.exists())
        G(Account, team=team)
        self.assertEquals(Entity.objects.count(), 2)
        self.assertEquals(EntityRelationship.objects.count(), 1)

    def test_optimal_queries_registered_entity_with_no_qset(self):
        """
        Tests that the optimal number of queries are performed when syncing a single entity that
        did not register a queryset.
        """
        team_group = G(TeamGroup)

        ContentType.objects.clear_cache()
        with self.assertNumQueries(15):
            team_group.save()

    def test_optimal_queries_registered_entity_w_qset(self):
        """
        Tests that the entity is refetch with its queryset when syncing an individual entity.
        """
        account = G(Account)

        ContentType.objects.clear_cache()
        with self.assertNumQueries(18):
            account.save()

    def test_sync_all_optimal_queries(self):
        """
        Tests optimal queries of syncing all entities.
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

        # Use an entity registry that only has accounts and teams. This ensures that other registered
        # entity models dont pollute the test case
        new_registry = EntityRegistry()
        new_registry.register_entity(AccountConfig)
        new_registry.register_entity(TeamConfig)

        with patch('entity.sync.entity_registry') as mock_entity_registry:
            mock_entity_registry.entity_registry = new_registry.entity_registry
            ContentType.objects.clear_cache()
            with self.assertNumQueries(20):
                sync_entities()

        self.assertEquals(Entity.objects.filter(entity_type=ContentType.objects.get_for_model(Account)).count(), 5)
        self.assertEquals(Entity.objects.filter(entity_type=ContentType.objects.get_for_model(Team)).count(), 2)
        self.assertEquals(Entity.objects.all().count(), 7)

        # There should be four entity relationships since four accounts have teams
        self.assertEquals(EntityRelationship.objects.all().count(), 4)


class DeferEntitySyncingTests(EntityTestCase):
    """
    Tests the defer entity syncing decorator
    """

    def test_defer(self):
        @defer_entity_syncing
        def test_method(test, count=5, sync_all=False):
            # Create some entities
            for i in range(count):
                Account.objects.create()

            if sync_all:
                sync_entities()

            # Assert that we do not have any entities
            test.assertEquals(Entity.objects.all().count(), 0)

        # Call the test method
        test_method(self, count=5)

        # Assert that after the method was run we did sync the entities
        self.assertEquals(Entity.objects.all().count(), 5)

        # Delete all entities
        Entity.all_objects.all()._raw_delete(Entity.objects.db)

        # Call the method again syncing all
        test_method(self, count=0, sync_all=True)

        # Assert that after the method was run we did sync the entities
        self.assertEquals(Entity.objects.all().count(), 5)

        # Assert that we restored the defer flag
        self.assertFalse(sync_entities.defer)

        # Assert that we cleared the buffer
        self.assertEqual(sync_entities.buffer, {})

    def test_defer_nothing_synced(self):
        """
        Test the defer decorator when nothing is synced
        """

        @defer_entity_syncing
        def test_method(test):
            # Assert that we do not have any entities
            test.assertEquals(Entity.objects.all().count(), 0)

        # Call the test method
        with patch('entity.sync.sync_entities') as mock_sync_entities:
            # Call the method that does no syncing
            test_method(self)

            # Ensure that we did not call sync entities
            self.assertFalse(mock_sync_entities.called)


class SuppressEntitySyncingTests(EntityTestCase):
    """
    Tests the suppress entity syncing decorator
    """

    def test_defer(self):
        @suppress_entity_syncing
        def test_method(test, count):
            # Create some entities
            for i in range(count):
                Account.objects.create()

            # Assert that we do not have any entities
            test.assertEquals(Entity.objects.all().count(), 0)

        # Call the test method
        test_method(self, count=5)

        # Assert that after the method was run we did sync the entities
        self.assertEquals(Entity.objects.all().count(), 0)

        # Assert that we restored the suppress flag
        self.assertFalse(sync_entities.suppress)


class TransactionAtomicWithRetryTests(EntityTestCase):
    """
    Test the transaction_atomic_with_retry decorator
    """

    def test_retry_operational_error(self):
        exception_mock = MagicMock()
        exception_mock.side_effect = db.utils.OperationalError()

        @transaction_atomic_with_retry()
        def test_func():
            exception_mock()

        with self.assertRaises(db.utils.OperationalError):
            test_func()

        self.assertEqual(
            len(exception_mock.mock_calls),
            6
        )

    def test_retry_other_error(self):
        exception_mock = MagicMock()
        exception_mock.side_effect = Exception()

        @transaction_atomic_with_retry()
        def test_func():
            exception_mock()

        with self.assertRaises(Exception):
            test_func()
        exception_mock.assert_called_once_with()
