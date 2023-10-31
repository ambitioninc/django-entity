from django.contrib.contenttypes.models import ContentType
from django_dynamic_fixture import G, N
from django.test import TestCase
from entity.sync import sync_entities

from entity.signal_handlers import turn_off_syncing, turn_on_syncing

from entity.models import (
    Entity, EntityKind, EntityRelationship, EntityGroup, EntityGroupMembership, get_entities_by_kind
)
from entity.tests.models import Account, Team, TeamGroup, Competitor
from entity.tests.utils import EntityTestCase


class EntityKindManagerTest(EntityTestCase):
    """
    Tests the active and all entity kind managers.
    """
    def test_only_active(self):
        G(EntityKind, is_active=False)
        active_ek = G(EntityKind, is_active=True)
        self.assertEqual([active_ek], list(EntityKind.objects.all()))

    def test_all_objects(self):
        inactive_ek = G(EntityKind, is_active=False)
        active_ek = G(EntityKind, is_active=True)
        self.assertEqual(set([active_ek, inactive_ek]), set(EntityKind.all_objects.all()))


class EntityKindTest(EntityTestCase):
    """
    Tests the EntityKind model.
    """
    def test_unicode(self):
        ek = N(EntityKind, display_name='hello')
        self.assertEqual(u'{0}'.format(ek), u'hello')

    def test_regular_delete(self):
        """
        Regular deletion should deactivate the entity kind.
        """
        ek = G(EntityKind, is_active=True)
        ek.delete()
        self.assertFalse(ek.is_active)


class TestActiveEntityManager(EntityTestCase):
    def test_filters_active_by_default(self):
        """
        Tests that active entities are returned by default when accessing Entity.objects
        """
        e = G(Entity, is_active=True)
        G(Entity, is_active=False)
        self.assertEqual([e], list(Entity.objects.all()))


class TestAllEntityManager(EntityTestCase):
    """
    Tests custom function in the AllEntityManager class.
    """
    def setUp(self):
        super(TestAllEntityManager, self).setUp()
        self.account_type = ContentType.objects.get_for_model(Account)
        self.account_kind = G(EntityKind, name='tests.account')
        self.team_type = ContentType.objects.get_for_model(Team)
        self.team_kind = G(EntityKind, name='tests.team')
        self.team_group_type = ContentType.objects.get_for_model(TeamGroup)
        self.team_group_kind = G(EntityKind, name='tests.teamgroup')
        self.competitor_type = ContentType.objects.get_for_model(Competitor)
        self.competitor_kind = G(EntityKind, name='tests.competitor')

    def test_manager_cache_relationships(self):
        """
        Tests a retrieval of cache relationships on the manager and verifies it results in the smallest amount of
        queries
        """
        team = Team.objects.create()
        for i in range(5):
            Account.objects.create(team=team)

        # Five queries should happen here - one for all entities, two for EntityRelationships,
        # and two more for entities in the relationships
        with self.assertNumQueries(5):
            entities = Entity.objects.cache_relationships()
            for entity in entities:
                self.assertTrue(len(list(entity.get_super_entities())) >= 0)
                self.assertTrue(len(list(entity.get_sub_entities())) >= 0)
        self.assertEqual(entities.count(), 6)

    def test_manager_cache_relationships_only_sub(self):
        """
        Tests a retrieval of cache relationships on the manager and verifies it results in the smallest amount of
        queries when only caching sub entities.
        """
        team = Team.objects.create()
        for i in range(5):
            Account.objects.create(team=team)

        # Five queries should happen here - one for all entities, two for EntityRelationships,
        # and two more for entities in the relationships
        with self.assertNumQueries(3):
            entities = Entity.objects.cache_relationships(cache_super=False)
            for entity in entities:
                self.assertTrue(len(list(entity.get_sub_entities())) >= 0)
        self.assertEqual(entities.count(), 6)

    def test_manager_cache_relationships_only_super(self):
        """
        Tests a retrieval of cache relationships on the manager and verifies it results in the smallest amount of
        queries when only caching super entities.
        """
        team = Team.objects.create()
        for i in range(5):
            Account.objects.create(team=team)

        # Five queries should happen here - one for all entities, two for EntityRelationships,
        # and two more for entities in the relationships
        with self.assertNumQueries(3):
            entities = Entity.objects.cache_relationships(cache_sub=False)
            for entity in entities:
                self.assertTrue(len(list(entity.get_super_entities())) >= 0)
        self.assertEqual(entities.count(), 6)

    def test_manager_cache_relationships_none(self):
        """
        Tests a retrieval of cache relationships on the manager and verifies it results in the smallest amount of
        queries when super and sub are set to false
        """
        team = Team.objects.create()
        for i in range(5):
            Account.objects.create(team=team)

        # Five queries should happen here - one for all entities, two for EntityRelationships,
        # and two more for entities in the relationships
        with self.assertNumQueries(1):
            entities = Entity.objects.cache_relationships(cache_sub=False, cache_super=False)
            self.assertTrue(len(entities) > 0)
        self.assertEqual(entities.count(), 6)

    def test_queryset_cache_relationships(self):
        """
        Tests a retrieval of cache relationships on the queryset and verifies it results in the smallest amount of
        queries
        """
        team = Team.objects.create()
        for i in range(5):
            Account.objects.create(team=team)

        entity_ids = [i.id for i in Entity.objects.all()]
        # Five queries should happen here - 1 for the Entity filter, two for EntityRelationships, and two more
        # for entities in those relationships
        with self.assertNumQueries(5):
            entities = Entity.objects.filter(id__in=entity_ids).cache_relationships()
            for entity in entities:
                self.assertTrue(len(list(entity.get_super_entities())) >= 0)
                self.assertTrue(len(list(entity.get_sub_entities())) >= 0)
        self.assertEqual(entities.count(), 6)

    def test_cache_subset(self):
        """
        Tests that caching still operates the same on an entity subset call.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        for i in range(5):
            Account.objects.create(team=team)

        # Five queries should happen here - 1 for the Entity filter, two for EntityRelationships, and one more
        # for entities in those relationships (since no sub relationships exist)
        with self.assertNumQueries(4):
            entities = Entity.objects.is_sub_to_all(team_entity).cache_relationships()
            for entity in entities:
                self.assertTrue(len(list(entity.get_super_entities())) == 1)
                self.assertTrue(len(list(entity.get_sub_entities())) == 0)
            self.assertEqual(len(entities), 5)

    def test_get_for_obj(self):
        """
        Test retrieving an entity associated with an object.
        """
        # Create an account with no team
        account = Account.objects.create()
        # Get its resulting entity
        entity = Entity.objects.get(entity_type=ContentType.objects.get_for_model(account), entity_id=account.id)
        self.assertEqual(entity, Entity.objects.get_for_obj(account))

    def test_filter_manager_active(self):
        """
        Test filtering active entities directly from the manager.
        """
        # Create an active and inactive account
        account = Account.objects.create()
        Account.objects.create(is_active=False)
        # Get its resulting entity
        entity = Entity.objects.get_for_obj(account)
        self.assertEqual([entity], list(Entity.objects.active()))

    def test_filter_manager_inactive(self):
        """
        Test filtering inactive entities directly from the manager.
        """
        # Create an active and inactive account
        account = Account.objects.create()
        account = Account.objects.create(is_active=False)
        # Get its resulting entity
        entity = Entity.all_objects.get_for_obj(account)
        self.assertEqual([entity], list(Entity.all_objects.inactive()))

    def test_filter_queryset_active(self):
        """
        Test filtering active entities from a queryset.
        """
        # Create an active and inactive account
        active_entity = Entity.objects.get_for_obj(Account.objects.create())
        inactive_entity = Entity.all_objects.get_for_obj(Account.objects.create(is_active=False))
        self.assertEqual(
            [active_entity], list(Entity.objects.filter(id__in=[active_entity.id, inactive_entity.id]).active()))

    def test_filter_queryset_inactive(self):
        """
        Test filtering inactive entities from a queryset.
        """
        # Create an active and inactive account
        active_entity = Entity.objects.get_for_obj(Account.objects.create())
        inactive_entity = Entity.all_objects.get_for_obj(Account.objects.create(is_active=False))
        self.assertEqual(
            [inactive_entity],
            list(Entity.all_objects.filter(id__in=[active_entity.id, inactive_entity.id]).inactive()))

    def test_filter_manager_is_kind_none(self):
        """
        Tests filtering by entity kind when no kind is given.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        account_entities = [
            Entity.objects.get_for_obj(Account.objects.create(team=team))
            for i in range(5)
        ]
        self.assertEqual(set([team_entity] + account_entities), set(Entity.objects.is_any_kind()))

    def test_filter_manager_one_kind(self):
        """
        Tests filtering by entity kind when one kind is given.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        account_entities = set(
            Entity.objects.get_for_obj(Account.objects.create(team=team))
            for i in range(5)
        )
        self.assertEqual([team_entity], list(Entity.objects.is_any_kind(self.team_kind)))
        self.assertEqual(account_entities, set(Entity.objects.is_any_kind(self.account_kind)))

    def test_filter_manager_two_kinds(self):
        """
        Tests filtering by entity kind when two kinds are given.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        account_entities = set(
            Entity.objects.get_for_obj(Account.objects.create(team=team))
            for i in range(5)
        )
        self.assertEqual(
            account_entities.union([team_entity]), set(Entity.objects.is_any_kind(self.account_kind, self.team_kind)))

    def test_is_sub_to_all_kinds_none(self):
        # set up teams, groups and competitors
        team = Team.objects.create()
        group = TeamGroup.objects.create(name='group')
        competitor = Competitor.objects.create(name='competitor')

        # set up players with different compinations of team, group and competitor
        Account.objects.create(email='team_only', team=team)
        Account.objects.create(email='team_competitor', team=team, competitor=competitor)
        Account.objects.create(email='team_group', team=team, team_group=group)
        Account.objects.create(email='group_only', team_group=group)
        Account.objects.create(email='group_competitor', team_group=group, competitor=competitor)
        Account.objects.create(email='competitor_only', competitor=competitor)

        sorted_names = sorted([e.display_name for e in Entity.objects.is_sub_to_all_kinds()])
        expected_names = [
            u'competitor', u'competitor_only', u'group', u'group_competitor',
            u'group_only', u'team', u'team_competitor', u'team_group', u'team_only'
        ]
        self.assertEqual(sorted_names, expected_names)

    def test_is_sub_to_all_kinds_double(self):
        # set up teams, groups and competitors
        team = Team.objects.create()
        group = TeamGroup.objects.create(name='group')
        competitor = Competitor.objects.create(name='competitor')

        # set up players with different compinations of team, group and competitor
        Account.objects.create(email='team_only', team=team)
        Account.objects.create(email='team_competitor', team=team, competitor=competitor)
        Account.objects.create(email='team_group', team=team, team_group=group)
        Account.objects.create(email='group_only', team_group=group)
        Account.objects.create(email='group_competitor', team_group=group, competitor=competitor)
        Account.objects.create(email='competitor_only', competitor=competitor)

        # get kind model(s)
        team_kind = EntityKind.objects.get(name='tests.team')
        group_kind = EntityKind.objects.get(name='tests.teamgroup')

        sorted_names = sorted([e.display_name for e in Entity.objects.is_sub_to_all_kinds(group_kind, team_kind)])
        expected_names = [u'team_group']
        self.assertEqual(sorted_names, expected_names)

    def test_is_sub_to_all_kinds_single(self):
        # set up teams, groups and competitors
        team = Team.objects.create()
        group = TeamGroup.objects.create(name='group')
        competitor = Competitor.objects.create(name='competitor')

        # set up players with different compinations of team, group and competitor
        Account.objects.create(email='team_only', team=team)
        Account.objects.create(email='team_competitor', team=team, competitor=competitor)
        Account.objects.create(email='team_group', team=team, team_group=group)
        Account.objects.create(email='group_only', team_group=group)
        Account.objects.create(email='group_competitor', team_group=group, competitor=competitor)
        Account.objects.create(email='competitor_only', competitor=competitor)

        # get kind model(s)
        group_kind = EntityKind.objects.get(name='tests.teamgroup')

        sorted_names = sorted([e.display_name for e in Entity.objects.is_sub_to_all_kinds(group_kind)])
        expected_names = [u'group_competitor', u'group_only', u'team_group']
        self.assertEqual(sorted_names, expected_names)

    def test_is_sub_to_any_kind_none(self):
        # set up teams, groups and competitors
        team = Team.objects.create()
        group = TeamGroup.objects.create(name='group')
        competitor = Competitor.objects.create(name='competitor')

        # set up players with different compinations of team, group and competitor
        Account.objects.create(email='team_only', team=team)
        Account.objects.create(email='team_competitor', team=team, competitor=competitor)
        Account.objects.create(email='team_group', team=team, team_group=group)
        Account.objects.create(email='group_only', team_group=group)
        Account.objects.create(email='group_competitor', team_group=group, competitor=competitor)
        Account.objects.create(email='competitor_only', competitor=competitor)

        sorted_names = sorted([e.display_name for e in Entity.objects.is_sub_to_any_kind()])
        expected_names = [
            u'competitor', u'competitor_only', u'group', u'group_competitor',
            u'group_only', u'team', u'team_competitor', u'team_group', u'team_only'
        ]
        self.assertEqual(sorted_names, expected_names)

    def test_is_sub_to_any_kind_single(self):
        # set up teams, groups and competitors
        team = Team.objects.create()
        group = TeamGroup.objects.create(name='group')
        competitor = Competitor.objects.create(name='competitor')

        # set up players with different compinations of team, group and competitor
        Account.objects.create(email='team_only', team=team)
        Account.objects.create(email='team_competitor', team=team, competitor=competitor)
        Account.objects.create(email='team_group', team=team, team_group=group)
        Account.objects.create(email='group_only', team_group=group)
        Account.objects.create(email='group_competitor', team_group=group, competitor=competitor)
        Account.objects.create(email='competitor_only', competitor=competitor)

        # get kind model(s)
        group_kind = EntityKind.objects.get(name='tests.teamgroup')

        sorted_names = sorted([e.display_name for e in Entity.objects.is_sub_to_any_kind(group_kind)])
        expected_names = [u'group_competitor', u'group_only', u'team_group']
        self.assertEqual(sorted_names, expected_names)

    def test_is_sub_to_any_kind_double(self):
        # set up teams, groups and competitors
        team = Team.objects.create()
        group = TeamGroup.objects.create(name='group')
        competitor = Competitor.objects.create(name='competitor')

        # set up players with different compinations of team, group and competitor
        Account.objects.create(email='team_only', team=team)
        Account.objects.create(email='team_competitor', team=team, competitor=competitor)
        Account.objects.create(email='team_group', team=team, team_group=group)
        Account.objects.create(email='group_only', team_group=group)
        Account.objects.create(email='group_competitor', team_group=group, competitor=competitor)
        Account.objects.create(email='competitor_only', competitor=competitor)

        # get kind model(s)
        team_kind = EntityKind.objects.get(name='tests.team')
        group_kind = EntityKind.objects.get(name='tests.teamgroup')

        sorted_names = sorted([e.display_name for e in Entity.objects.is_sub_to_any_kind(team_kind, group_kind)])
        expected_names = [u'group_competitor', u'group_only', u'team_competitor', u'team_group', u'team_only']
        self.assertEqual(sorted_names, expected_names)

    def test_filter_queryset_two_kinds(self):
        """
        Tests filtering by entity kind when two kinds are given on a queryset.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        account_entities = set(
            Entity.objects.get_for_obj(Account.objects.create(team=team))
            for i in range(5)
        )
        self.assertEqual(
            account_entities.union([team_entity]),
            set(
                Entity.objects.filter(id__in=(i.id for i in account_entities.union([team_entity]))).is_any_kind(
                    self.account_kind, self.team_kind)
            ))

    def test_filter_manager_is_not_kind_two(self):
        """
        Tests filtering by entity kind when two kinds are given.
        """
        team = Team.objects.create()
        for i in range(5):
            Account.objects.create(team=team)
        self.assertEqual([], list(Entity.objects.is_not_any_kind(self.team_kind, self.account_kind)))

    def test_filter_manager_is_not_kind_one(self):
        """
        Tests filtering by entity kind when one kind is given.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        account_entities = set(
            Entity.objects.get_for_obj(Account.objects.create(team=team))
            for i in range(5)
        )
        self.assertEqual([team_entity], list(Entity.objects.is_not_any_kind(self.account_kind)))
        self.assertEqual(account_entities, set(Entity.objects.is_not_any_kind(self.team_kind)))

    def test_filter_manager_is_not_kind_none(self):
        """
        Tests filtering by entity kind when no kinds are given.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        account_entities = set(
            Entity.objects.get_for_obj(Account.objects.create(team=team))
            for i in range(5)
        )
        self.assertEqual(
            account_entities.union([team_entity]), set(Entity.objects.is_not_any_kind()))

    def test_filter_queryset_two_is_not_kinds(self):
        """
        Tests filtering by entity type when two kinds are given on a queryset.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        account_entities = set(
            Entity.objects.get_for_obj(Account.objects.create(team=team))
            for i in range(5)
        )
        self.assertEqual(
            [],
            list(Entity.objects.filter(id__in=(i.id for i in account_entities.union([team_entity]))).is_not_any_kind(
                self.account_kind, self.team_kind))
        )

    def test_is_sub_to_all_none(self):
        """
        Tests the base case of is_sub_to_all on no super entities.
        """
        # Create test accounts that have three types of super entities
        team = Team.objects.create()
        team2 = Team.objects.create()
        team_group = TeamGroup.objects.create()
        competitor = Competitor.objects.create()

        # Create accounts that have four super entities
        for i in range(5):
            Account.objects.create(competitor=competitor, team=team, team2=team2, team_group=team_group)

        # Create accounts that have no super entities
        for i in range(5):
            Entity.objects.get_for_obj(Account.objects.create())

        self.assertEqual(
            set(Entity.objects.all()), set(Entity.objects.is_sub_to_all()))

    def test_is_sub_to_all_none_is_any_kind(self):
        """
        Tests the base case of is_sub_to_all on no super entities with a kind specified.
        """
        # Create test accounts that have three types of super entities
        team = Team.objects.create()
        team2 = Team.objects.create()
        team_group = TeamGroup.objects.create()
        competitor = Competitor.objects.create()

        # Create accounts that have four super entities
        for i in range(5):
            Account.objects.create(competitor=competitor, team=team, team2=team2, team_group=team_group)

        # Create accounts that have no super entities
        for i in range(5):
            Entity.objects.get_for_obj(Account.objects.create())

        self.assertEqual(
            set(Entity.objects.filter(entity_type=self.account_type)),
            set(Entity.objects.is_sub_to_all().is_any_kind(self.account_kind)))

    def test_is_sub_to_all_manager(self):
        """
        Tests the is_sub_to_all for an entity directly from the entity manager.
        """
        # Create test accounts that have three types of super entities
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        team2 = Team.objects.create()
        team2_entity = Entity.objects.get_for_obj(team2)
        team_group = TeamGroup.objects.create()
        team_group_entity = Entity.objects.get_for_obj(team_group)
        competitor = Competitor.objects.create()
        competitor_entity = Entity.objects.get_for_obj(competitor)

        # Create accounts that have four super entities
        entities_4se = set(
            Entity.objects.get_for_obj(
                Account.objects.create(competitor=competitor, team=team, team2=team2, team_group=team_group))
            for i in range(5)
        )
        # Create test accounts that have two super entities
        entities_2se1 = set(
            Entity.objects.get_for_obj(Account.objects.create(competitor=competitor, team_group=team_group))
            for i in range(5)
        )
        entities_2se2 = set(
            Entity.objects.get_for_obj(Account.objects.create(competitor=competitor, team=team)) for i in range(5)
        )
        # Create test accounts that have one super entity
        entities_1se = set(Entity.objects.get_for_obj(Account.objects.create(team=team)) for i in range(5))

        # Test various subset results
        self.assertEqual(
            entities_4se, set(Entity.objects.is_sub_to_all(
                team_entity, team2_entity, team_group_entity, competitor_entity)))
        self.assertEqual(
            entities_1se | entities_2se2 | entities_4se, set(Entity.objects.is_sub_to_all(team_entity)))
        self.assertEqual(
            entities_4se | entities_2se2, set(Entity.objects.is_sub_to_all(team_entity, competitor_entity)))
        self.assertEqual(
            entities_4se | entities_2se1, set(Entity.objects.is_sub_to_all(team_group_entity)))
        self.assertEqual(
            entities_4se | entities_2se1 | entities_2se2,
            set(Entity.objects.is_sub_to_all(competitor_entity)))

    def test_is_sub_to_all_queryset(self):
        """
        Tests the subset of super entity types for an entity from a queryset.
        """
        # Create test accounts that have three types of super entities
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        team2 = Team.objects.create()
        team2_entity = Entity.objects.get_for_obj(team2)
        team_group = TeamGroup.objects.create()
        team_group_entity = Entity.objects.get_for_obj(team_group)
        competitor = Competitor.objects.create()
        competitor_entity = Entity.objects.get_for_obj(competitor)

        # Create accounts that have four super entities
        entities_4se = list(
            Entity.objects.get_for_obj(
                Account.objects.create(competitor=competitor, team=team, team2=team2, team_group=team_group))
            for i in range(5)
        )

        # Test subset results
        self.assertEqual(
            set(entities_4se).difference([entities_4se[0]]),
            set(Entity.objects.exclude(id=entities_4se[0].id).is_sub_to_all(
                team_entity, team2_entity, team_group_entity, competitor_entity)))

    def test_is_sub_to_all_queryset_num_queries(self):
        """
        Tests that is_sub_to_all only results in one query.
        """
        # Create test accounts that have three types of super entities
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        team2 = Team.objects.create()
        team2_entity = Entity.objects.get_for_obj(team2)
        team_group = TeamGroup.objects.create()
        team_group_entity = Entity.objects.get_for_obj(team_group)
        competitor = Competitor.objects.create()
        competitor_entity = Entity.objects.get_for_obj(competitor)

        # Create accounts that have four super entities
        entities_4se = list(
            Entity.objects.get_for_obj(
                Account.objects.create(competitor=competitor, team=team, team2=team2, team_group=team_group))
            for i in range(5)
        )

        with self.assertNumQueries(1):
            entities = set(Entity.objects.exclude(id=entities_4se[0].id).is_sub_to_all(
                team_entity, team2_entity, team_group_entity, competitor_entity))

        # Test subset results
        self.assertEqual(set(entities_4se).difference([entities_4se[0]]), entities)

    def test_is_sub_to_any_none(self):
        """
        Tests the base case of is_sub_to_any on no super entities.
        """
        # Create test accounts that have three types of super entities
        team = Team.objects.create()
        team2 = Team.objects.create()
        team_group = TeamGroup.objects.create()
        competitor = Competitor.objects.create()

        # Create accounts that have four super entities
        for i in range(5):
            Account.objects.create(competitor=competitor, team=team, team2=team2, team_group=team_group)

        # Create accounts that have no super entities
        for i in range(5):
            Entity.objects.get_for_obj(Account.objects.create())

        self.assertEqual(
            set(Entity.objects.all()), set(Entity.objects.is_sub_to_any()))

    def test_is_sub_to_any_queryset(self):
        """
        Tests the is_sub_to_any for an entity from a queryset.
        """
        # Create test accounts that have three types of super entities
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        team2 = Team.objects.create()
        team2_entity = Entity.objects.get_for_obj(team2)
        team_group = TeamGroup.objects.create()
        team_group_entity = Entity.objects.get_for_obj(team_group)
        competitor = Competitor.objects.create()
        competitor_entity = Entity.objects.get_for_obj(competitor)

        # Create accounts that have four super entities
        entities_4se = list(
            Entity.objects.get_for_obj(
                Account.objects.create(competitor=competitor, team=team, team2=team2, team_group=team_group))
            for i in range(5)
        )

        # Test subset results
        self.assertEqual(
            set(entities_4se).difference([entities_4se[0]]),
            set(Entity.objects.exclude(id=entities_4se[0].id).is_sub_to_any(
                team_entity, team2_entity, team_group_entity, competitor_entity)))

    def test_is_sub_to_any_limited_results(self):
        """
        Tests the is_sub_to_any for an entity from a queryset where the is_sub_to_any returns less than all
        of the entities created.
        """
        # Create test accounts that have three types of super entities
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        team2 = Team.objects.create()

        # Create accounts that have super entites of team and team2
        entities_w_team = list(
            Entity.objects.get_for_obj(Account.objects.create(team=team))
            for i in range(5)
        )
        for i in range(5):
            Account.objects.create(team=team2)

        # Test subset results
        self.assertEqual(set(entities_w_team), set(Entity.objects.is_sub_to_any(team_entity)))


class TestEntityModel(EntityTestCase):
    """
    Tests custom functionality in the Entity model.
    """
    def test_get_super_entities_none(self):
        """
        Tests that super entities are retrieved for mirrored entities that
        have no super entities
        """
        # Create an account with no team
        account = Account.objects.create()
        # Get its resulting entity
        entity = Entity.objects.get_for_obj(account)
        # Get its super entities. It should be an empty list
        self.assertEqual(list(entity.get_super_entities()), [])

    def test_get_super_entities_one(self):
        """
        Tests retrieval of super entities when an entity has exactly one.
        """
        # Create a team and an account with the team as a super entity.
        team = Team.objects.create()
        account = Account.objects.create(team=team)
        # Get the entity of the account and the team
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        # Verify that the super entities of the account is the team
        self.assertEqual(list(account_entity.get_super_entities()), [team_entity])

    def test_get_sub_entities_none(self):
        """
        Tests retrieval of sub entities when an entity has none.
        """
        # Create a team
        team = Team.objects.create()
        # Get the entity of the team
        team_entity = Entity.objects.get_for_obj(team)
        # Verify that the sub entities of the team is an empty list
        self.assertEqual(list(team_entity.get_super_entities()), [])

    def test_get_sub_entities_one(self):
        """
        Tests retrieval of sub entities when an entity has exactly one.
        """
        # Create a team and an account with the team as a super entity.
        team = Team.objects.create()
        account = Account.objects.create(team=team)
        # Get the entity of the account and the team
        account_entity = Entity.objects.get_for_obj(account)
        team_entity = Entity.objects.get_for_obj(team)
        # Verify that the sub entities of the team is the account
        self.assertEqual(list(team_entity.get_sub_entities()), [account_entity])

    def test_unicode(self):
        """
        Tests that the unicode method returns the display name of the entity.
        """
        account = Account.objects.create(email='hi')
        entity = Entity.objects.get_for_obj(account)
        entity_unicode = entity.__str__()
        self.assertEqual(entity_unicode, 'hi')


class EntityGroupAllEntitiesTest(EntityTestCase):
    def setUp(self):
        super(EntityGroupAllEntitiesTest, self).setUp()
        # Create three super entities, each with two sub
        # entities. THere are two entity kinds. Super entity 1 has two
        # sub entities of the first kind, super entity 2 has subs of
        # two different kinds, and super entity three has two of the
        # second kind.
        self.kind1, self.kind2 = G(EntityKind), G(EntityKind)
        self.super_entities = [G(Entity) for _ in range(3)]
        self.sub_entities = [
            G(Entity, entity_kind=k)
            for k in [self.kind1] * 3 + [self.kind2] * 3
        ]
        for i, sub in enumerate(self.sub_entities):
            sup = self.super_entities[i // 2]
            G(EntityRelationship, sub_entity=sub, super_entity=sup)

        self.group = G(EntityGroup)

    def test_logic_string(self):
        """
        Given 10 users User 0 - User 9 and 4 groups Group A - Group D
        Group A: 0, 1, 2
        Group B: 1, 2, 3
        Group C: 4, 5, 6
        Group D: 6, 7, 8

        Memberships:
        1. User in Group A
        2. User in Group B
        3. User in Group C
        4. User in Group D
        5. User = User 1
        6. User = User 9

        Logic: (1 AND 2) OR (3 AND 4) AND NOT(5) OR 6
        ((0, 1, 2) AND (1, 2, 3)) OR ((4, 5, 6) AND (6, 7, 8)) AND NOT(1) OR (9)
        (1, 2) OR (6) AND NOT(1) OR 9
        (1, 2, 6) AND NOT(1) OR 9
        2, 6, 9
        """
        super_entity_kind = G(EntityKind)
        sub_entity_kind = G(EntityKind)
        super_entity_a = G(Entity, entity_kind=super_entity_kind)
        super_entity_b = G(Entity, entity_kind=super_entity_kind)
        super_entity_c = G(Entity, entity_kind=super_entity_kind)
        super_entity_d = G(Entity, entity_kind=super_entity_kind)
        sub_entities = [
            G(Entity, entity_kind=sub_entity_kind)
            for _ in range(10)
        ]

        # Create the relationships
        relationships = [
            EntityRelationship(sub_entity=sub_entities[0], super_entity=super_entity_a),
            EntityRelationship(sub_entity=sub_entities[1], super_entity=super_entity_a),
            EntityRelationship(sub_entity=sub_entities[2], super_entity=super_entity_a),

            EntityRelationship(sub_entity=sub_entities[1], super_entity=super_entity_b),
            EntityRelationship(sub_entity=sub_entities[2], super_entity=super_entity_b),
            EntityRelationship(sub_entity=sub_entities[3], super_entity=super_entity_b),

            EntityRelationship(sub_entity=sub_entities[4], super_entity=super_entity_c),
            EntityRelationship(sub_entity=sub_entities[5], super_entity=super_entity_c),
            EntityRelationship(sub_entity=sub_entities[6], super_entity=super_entity_c),

            EntityRelationship(sub_entity=sub_entities[6], super_entity=super_entity_d),
            EntityRelationship(sub_entity=sub_entities[7], super_entity=super_entity_d),
            EntityRelationship(sub_entity=sub_entities[8], super_entity=super_entity_d),
        ]
        EntityRelationship.objects.bulk_create(relationships)

        # Create the entity group
        entity_group = G(EntityGroup, logic_string='((1 AND 2) OR (3 AND 4)) AND NOT(5) OR 6')

        # Create the memberships -- two memberships of all subs under a kind
        G(EntityGroupMembership, entity_group=entity_group, sub_entity_kind=sub_entity_kind, entity=super_entity_a)
        G(EntityGroupMembership, entity_group=entity_group, sub_entity_kind=sub_entity_kind, entity=super_entity_b)
        G(EntityGroupMembership, entity_group=entity_group, sub_entity_kind=sub_entity_kind, entity=super_entity_c)
        G(EntityGroupMembership, entity_group=entity_group, sub_entity_kind=sub_entity_kind, entity=super_entity_d)
        G(EntityGroupMembership, entity_group=entity_group, sub_entity_kind=None, entity=sub_entities[1])
        G(EntityGroupMembership, entity_group=entity_group, sub_entity_kind=None, entity=sub_entities[9])

        entity_ids = entity_group.get_all_entities()
        self.assertEqual(entity_ids, set([
            sub_entities[2].id,
            sub_entities[6].id,
            sub_entities[9].id,
        ]))

    def test_logic_string_not(self):
        """
        Verifies that the universal set is properly fetched and used to NOT a set
        Group A: 0, 1, 2
        NOT(A) = 3, 4, 5, 6, 7, 8

        Memberships:
        1. User in Group A

        Logic: NOT(1)
        (3, 4, 5, 6, 7, 8)
        """
        super_entity_kind = G(EntityKind)
        sub_entity_kind = G(EntityKind)
        super_entity_a = G(Entity, entity_kind=super_entity_kind)
        sub_entities = [
            G(Entity, entity_kind=sub_entity_kind)
            for _ in range(10)
        ]

        # Create the relationships
        relationships = [
            EntityRelationship(sub_entity=sub_entities[0], super_entity=super_entity_a),
            EntityRelationship(sub_entity=sub_entities[1], super_entity=super_entity_a),
            EntityRelationship(sub_entity=sub_entities[2], super_entity=super_entity_a),
        ]
        EntityRelationship.objects.bulk_create(relationships)

        # Create the entity group
        entity_group = G(EntityGroup, logic_string='NOT(1)')

        # Create the membership
        G(EntityGroupMembership, entity_group=entity_group, sub_entity_kind=sub_entity_kind, entity=super_entity_a)

        entity_ids = entity_group.get_all_entities()
        self.assertEqual(entity_ids, set([
            sub_entities[3].id,
            sub_entities[4].id,
            sub_entities[5].id,
            sub_entities[6].id,
            sub_entities[7].id,
            sub_entities[8].id,
            sub_entities[9].id,
        ]))

    def test_individual_entities_returned(self):
        e = self.super_entities[0]
        G(EntityGroupMembership, entity_group=self.group, entity=e, sub_entity_kind=None)
        result = list(self.group.all_entities().order_by('id'))
        expected = [e]
        self.assertEqual(result, expected)

    def test_sub_entity_group_entities_returned(self):
        e = self.super_entities[0]
        G(
            EntityGroupMembership, entity_group=self.group,
            entity=e, sub_entity_kind=self.kind1)
        result = list(self.group.all_entities().order_by('id'))
        expected = self.sub_entities[0:2]
        self.assertEqual(result, expected)

    def test_sub_entity_group_entities_filters_by_kind(self):
        e = self.super_entities[1]
        G(EntityGroupMembership, entity_group=self.group,
          entity=e, sub_entity_kind=self.kind1)
        result = list(self.group.all_entities().order_by('id'))
        expected = [self.sub_entities[2]]
        self.assertEqual(result, expected)

    def test_combined_returned(self):
        e = self.super_entities[1]
        G(EntityGroupMembership, entity_group=self.group,
          entity=e, sub_entity_kind=self.kind1)
        G(EntityGroupMembership, entity_group=self.group,
          entity=e, sub_entity_kind=None)
        result = list(self.group.all_entities().order_by('id'))
        expected = [e, self.sub_entities[2]]

        self.assertEqual(result, expected)

    def test_all_entities_of_a_kind_returned(self):
        """
        When a group has a sub_entity_kind but a null entity, it should return all entities of that kind
        """
        G(EntityGroupMembership, entity_group=self.group, sub_entity_kind=self.kind1)
        result = list(self.group.all_entities().order_by('id'))
        expected = [self.sub_entities[0], self.sub_entities[1], self.sub_entities[2]]

        self.assertEqual(result, expected)

    def test_filters_groups(self):
        other_group = G(EntityGroup)
        e = self.super_entities[1]
        G(EntityGroupMembership, entity_group=self.group,
          entity=e, sub_entity_kind=self.kind1)
        G(EntityGroupMembership, entity_group=self.group,
          entity=e, sub_entity_kind=None)
        G(EntityGroupMembership, entity_group=other_group,
          entity=e, sub_entity_kind=None)
        result = self.group.all_entities().count()
        expected = 2
        self.assertEqual(result, expected)

    def test_number_of_queries(self):
        e1 = self.super_entities[1]
        e2 = self.super_entities[2]
        sub1 = self.sub_entities[0]

        # Individual memberships
        G(EntityGroupMembership, entity_group=self.group,
          entity=e1, sub_entity_kind=None)
        G(EntityGroupMembership, entity_group=self.group,
          entity=sub1, sub_entity_kind=None)

        # Group memberships
        G(EntityGroupMembership, entity_group=self.group,
          entity=e1, sub_entity_kind=self.kind1)
        G(EntityGroupMembership, entity_group=self.group,
          entity=e2, sub_entity_kind=self.kind2)

        with self.assertNumQueries(4):
            list(self.group.all_entities())


class EntityGroupAddEntityTest(EntityTestCase):
    def test_adds_entity(self):
        group = G(EntityGroup)
        e = G(Entity)
        membership = group.add_entity(e)
        count = EntityGroupMembership.objects.filter(entity_group=group).count()
        expected = 1
        self.assertEqual(count, expected)
        self.assertIsInstance(membership, EntityGroupMembership)


class EntityGroupBulkAddEntitiesTest(EntityTestCase):
    def test_bulk_adds(self):
        group = G(EntityGroup)
        e1, e2 = G(Entity), G(Entity)
        k = G(EntityKind)
        to_add = [(e1, k), (e2, None)]
        membership = group.bulk_add_entities(to_add)
        count = EntityGroupMembership.objects.filter(entity_group=group).count()
        expected = 2
        self.assertEqual(count, expected)
        self.assertIsInstance(membership[0], EntityGroupMembership)

    def test_bulk_add_none_entity(self):
        group = EntityGroup.objects.create()
        e = G(Entity)
        k = G(EntityKind)
        group.bulk_add_entities([(None, k), (e, k), (e, None)])
        count = EntityGroupMembership.objects.filter(entity_group=group).count()
        self.assertEqual(count, 3)


class EntityGroupRemoveEntityTest(EntityTestCase):
    def setUp(self):
        self.group = G(EntityGroup)
        self.e1, self.e2 = G(Entity), G(Entity)
        self.k = G(EntityKind)
        to_add = [(self.e1, self.k), (self.e2, None)]
        self.group.bulk_add_entities(to_add)

    def test_removes_only_selected_no_entity_kind(self):
        self.group.remove_entity(self.e2)
        member = EntityGroupMembership.objects.get(entity_group=self.group)
        expected = self.k
        self.assertEqual(member.sub_entity_kind, expected)

    def test_removes_only_selected_with_entity_kind(self):
        self.group.remove_entity(self.e1, self.k)
        member = EntityGroupMembership.objects.get(entity_group=self.group)
        expected = None
        self.assertEqual(member.sub_entity_kind, expected)


class EntityGroupBulkRemoveEntitiesTest(EntityTestCase):
    def setUp(self):
        self.group = G(EntityGroup)
        self.e1, self.e2, self.e3 = G(Entity), G(Entity), G(Entity)
        self.k = G(EntityKind)
        to_add = [(self.e1, self.k), (self.e2, None), (self.e3, self.k), (self.e3, None)]
        self.group.bulk_add_entities(to_add)

    def test_only_removes_selected(self):
        self.group.bulk_remove_entities([(self.e3, self.k), (self.e2, None)])
        count = EntityGroupMembership.objects.filter(entity_group=self.group).count()
        expected = 2
        self.assertEqual(count, expected)

    def test_num_queries(self):
        with self.assertNumQueries(2):
            self.group.bulk_remove_entities([(self.e3, self.k), (self.e2, None)])


class EntityGroupBulkOverwriteEntitiesTest(EntityTestCase):
    def setUp(self):
        self.group = G(EntityGroup)
        self.e1, self.e2, self.e3 = G(Entity), G(Entity), G(Entity)
        self.k = G(EntityKind)
        to_add = [(self.e1, self.k), (self.e2, None), (self.e3, self.k), (self.e3, None)]
        self.group.bulk_add_entities(to_add)

    def test_overwrites(self):
        to_overwrite = [(self.e1, None), (self.e2, self.k)]
        self.group.bulk_overwrite(to_overwrite)
        count = EntityGroupMembership.objects.filter(entity_group=self.group).count()
        new_members = EntityGroupMembership.objects.values_list('entity', 'sub_entity_kind')
        expected = 2
        self.assertEqual(count, expected)
        self.assertIn((self.e1.id, None), new_members)

    def test_bulk_overwrite_none_entity(self):
        group = EntityGroup.objects.create()
        group.bulk_overwrite([(None, self.k)])
        count = EntityGroupMembership.objects.filter(entity_group=group).count()
        self.assertEqual(count, 1)


class EntityGroupTest(TestCase):

    def test_get_all_entities(self):
        turn_off_syncing()

        account_type = ContentType.objects.get_for_model(Account)
        team_type = ContentType.objects.get_for_model(Team)

        # Set up teams
        teams = Team.objects.bulk_create([
            Team()
            for i in range(0, 3)
        ])

        # Set up accounts
        Account.objects.bulk_create([
            Account(team=teams[i % 3])
            for i in range(0, 20)
        ])

        # Turn on syncing and do a sync
        turn_on_syncing()

        sync_entities()

        account_entities = list(Entity.all_objects.filter(entity_type=account_type).order_by('entity_id'))
        account_kind = account_entities[0].entity_kind

        team_entities = list(Entity.all_objects.filter(entity_type=team_type).order_by('entity_id'))
        team_kind = team_entities[0].entity_kind

        # Create groups
        EntityGroup.objects.bulk_create([
            EntityGroup()
            for i in range(0, 6)
        ])

        # Refresh for django 1.9 because bulk create does not return ids
        entity_groups = list(EntityGroup.objects.order_by('id'))

        # Set up individual entity groups
        entity_groups[0].bulk_add_entities([
            [account_entities[0], None],
            [account_entities[1], None],
            [account_entities[2], None],
            [account_entities[3], None],
        ])
        entity_groups[1].bulk_add_entities([
            [account_entities[2], None],
            [account_entities[3], None],
            [account_entities[4], None],
            [account_entities[5], None],
        ])

        # Set up sub entity kind of super entity groups
        entity_groups[2].bulk_add_entities([
            [team_entities[0], account_kind],
            [team_entities[1], account_kind],
        ])

        entity_groups[3].bulk_add_entities([
            [team_entities[0], account_kind],
        ])

        # Set up sub entity kind groups
        # This group has two copies of the same set of all accounts as well as all teams
        entity_groups[4].bulk_add_entities([
            [None, account_kind],
            [None, account_kind],
            [None, team_kind],
        ])

        # This group has the same copy of all accounts
        entity_groups[5].bulk_add_entities([
            [None, account_kind],
        ])

        with self.assertNumQueries(4):
            membership_cache = EntityGroup.objects.get_membership_cache()
            entities_by_kind = get_entities_by_kind(membership_cache=membership_cache)

            for entity_group in entity_groups:
                entity_group.get_all_entities(membership_cache, entities_by_kind)

        with self.assertNumQueries(4):
            get_entities_by_kind()

        # Make sure to hit the no group cache case
        self.assertEqual(entity_groups[0].get_all_entities(membership_cache={1000: []}), set())

    def test_get_all_entities_active(self):
        """
        Makes sure only active entity ids are returned
        """
        turn_off_syncing()

        account_type = ContentType.objects.get_for_model(Account)
        team_type = ContentType.objects.get_for_model(Team)

        # Set up teams
        teams = Team.objects.bulk_create([
            Team()
            for i in range(0, 3)
        ])

        # Set up accounts
        accounts = Account.objects.bulk_create([
            Account(team=teams[i % 3])
            for i in range(0, 20)
        ])
        accounts[0].is_active = False
        accounts[0].save()

        # Turn on syncing and do a sync
        turn_on_syncing()

        sync_entities()

        account_entities = list(Entity.all_objects.filter(entity_type=account_type).order_by('entity_id'))

        # Create groups
        EntityGroup.objects.bulk_create([
            EntityGroup()
            for i in range(0, 6)
        ])

        # Refresh for django 1.9 because bulk create does not return ids
        entity_groups = list(EntityGroup.objects.order_by('id'))

        # Set up individual entity groups
        entity_groups[0].bulk_add_entities([
            [account_entities[0], None],
            [account_entities[1], None],
            [account_entities[2], None],
            [account_entities[3], None],
        ])

        # Group 0 consists of an inactive account (0) and 3 actives (1-3)
        self.assertEqual(len(entity_groups[0].get_all_entities()), 3)
        self.assertEqual(len(entity_groups[0].get_all_entities(is_active=False)), 1)
        self.assertEqual(len(entity_groups[0].get_all_entities(is_active=None)), 4)

        # Check the same thing for an entity group defined by a super entity and sub entity kind
        team_entities = list(Entity.all_objects.filter(entity_type=team_type).order_by('entity_id'))
        entity_groups[1].bulk_add_entities([
            [team_entities[0], account_entities[0].entity_kind]
        ])

        # Team 0 has accounts 0, 3, 6, 9, 12, 15, 18
        # account 0 is inactive
        self.assertEqual(len(entity_groups[1].get_all_entities()), 6)
        self.assertEqual(len(entity_groups[1].get_all_entities(is_active=False)), 1)
        self.assertEqual(len(entity_groups[1].get_all_entities(is_active=None)), 7)

        entity_ids = list(entity_groups[1].get_all_entities())

        # Make 3 more of them inactive
        entity_ids = [
            entity_id
            for entity_id in entity_ids[0:3]
        ]
        Entity.objects.filter(id__in=entity_ids).update(is_active=False)
        self.assertEqual(len(entity_groups[1].get_all_entities()), 3)
        self.assertEqual(len(entity_groups[1].get_all_entities(is_active=False)), 4)
        self.assertEqual(len(entity_groups[1].get_all_entities(is_active=None)), 7)

        # Set a super to inactive and make sure the active subs are ignored
        team_entities = list(Entity.all_objects.filter(entity_type=team_type).order_by('entity_id'))
        entity_groups[2].bulk_add_entities([
            [team_entities[1], account_entities[0].entity_kind]
        ])
        Entity.objects.filter(id=team_entities[1].id).update(is_active=False)

        # Nothing should be returned because the super is inactive which makes the group invalid
        self.assertEqual(len(entity_groups[2].get_all_entities()), 0)
        self.assertEqual(len(entity_groups[2].get_all_entities(is_active=False)), 0)
        self.assertEqual(len(entity_groups[2].get_all_entities(is_active=None)), 7)
