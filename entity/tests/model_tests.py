from django.contrib.contenttypes.models import ContentType
from django_dynamic_fixture import G, N
from entity.models import Entity, EntityKind

from .models import Account, Team, TeamGroup, Competitor
from .utils import EntityTestCase


class EntityKindManagerTest(EntityTestCase):
    """
    Tests the active and all entity kind managers.
    """
    def test_only_active(self):
        G(EntityKind, is_active=False)
        active_ek = G(EntityKind, is_active=True)
        self.assertEquals([active_ek], list(EntityKind.objects.all()))

    def test_all_objects(self):
        inactive_ek = G(EntityKind, is_active=False)
        active_ek = G(EntityKind, is_active=True)
        self.assertEquals(set([active_ek, inactive_ek]), set(EntityKind.all_objects.all()))


class EntityKindTest(EntityTestCase):
    """
    Tests the EntityKind model.
    """
    def test_unicode(self):
        ek = N(EntityKind, display_name='hello')
        self.assertEquals(u'{0}'.format(ek), u'hello')

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
        self.assertEquals([e], list(Entity.objects.all()))


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
        self.assertEquals(entities.count(), 6)

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
        self.assertEquals(entities.count(), 6)

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
        self.assertEquals(entities.count(), 6)

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
        self.assertEquals(entities.count(), 6)

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
        self.assertEquals(entities.count(), 6)

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
            self.assertEquals(len(entities), 5)

    def test_get_for_obj(self):
        """
        Test retrieving an entity associated with an object.
        """
        # Create an account with no team
        account = Account.objects.create()
        # Get its resulting entity
        entity = Entity.objects.get(entity_type=ContentType.objects.get_for_model(account), entity_id=account.id)
        self.assertEquals(entity, Entity.objects.get_for_obj(account))

    def test_filter_manager_active(self):
        """
        Test filtering active entities directly from the manager.
        """
        # Create an active and inactive account
        account = Account.objects.create()
        Account.objects.create(is_active=False)
        # Get its resulting entity
        entity = Entity.objects.get_for_obj(account)
        self.assertEquals([entity], list(Entity.objects.active()))

    def test_filter_manager_inactive(self):
        """
        Test filtering inactive entities directly from the manager.
        """
        # Create an active and inactive account
        account = Account.objects.create()
        account = Account.objects.create(is_active=False)
        # Get its resulting entity
        entity = Entity.all_objects.get_for_obj(account)
        self.assertEquals([entity], list(Entity.all_objects.inactive()))

    def test_filter_queryset_active(self):
        """
        Test filtering active entities from a queryset.
        """
        # Create an active and inactive account
        active_entity = Entity.objects.get_for_obj(Account.objects.create())
        inactive_entity = Entity.all_objects.get_for_obj(Account.objects.create(is_active=False))
        self.assertEquals(
            [active_entity], list(Entity.objects.filter(id__in=[active_entity.id, inactive_entity.id]).active()))

    def test_filter_queryset_inactive(self):
        """
        Test filtering inactive entities from a queryset.
        """
        # Create an active and inactive account
        active_entity = Entity.objects.get_for_obj(Account.objects.create())
        inactive_entity = Entity.all_objects.get_for_obj(Account.objects.create(is_active=False))
        self.assertEquals(
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
        self.assertEquals(set([team_entity] + account_entities), set(Entity.objects.is_any_kind()))

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
        self.assertEquals([team_entity], list(Entity.objects.is_any_kind(self.team_kind)))
        self.assertEquals(account_entities, set(Entity.objects.is_any_kind(self.account_kind)))

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
        self.assertEquals(
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
        self.assertEquals(
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
        self.assertEquals([], list(Entity.objects.is_not_any_kind(self.team_kind, self.account_kind)))

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
        self.assertEquals([team_entity], list(Entity.objects.is_not_any_kind(self.account_kind)))
        self.assertEquals(account_entities, set(Entity.objects.is_not_any_kind(self.team_kind)))

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
        self.assertEquals(
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
        self.assertEquals(
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

        self.assertEquals(
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

        self.assertEquals(
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
        self.assertEquals(
            entities_4se, set(Entity.objects.is_sub_to_all(
                team_entity, team2_entity, team_group_entity, competitor_entity)))
        self.assertEquals(
            entities_1se | entities_2se2 | entities_4se, set(Entity.objects.is_sub_to_all(team_entity)))
        self.assertEquals(
            entities_4se | entities_2se2, set(Entity.objects.is_sub_to_all(team_entity, competitor_entity)))
        self.assertEquals(
            entities_4se | entities_2se1, set(Entity.objects.is_sub_to_all(team_group_entity)))
        self.assertEquals(
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
        self.assertEquals(
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
        self.assertEquals(set(entities_4se).difference([entities_4se[0]]), entities)

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

        self.assertEquals(
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
        self.assertEquals(
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
        self.assertEquals(set(entities_w_team), set(Entity.objects.is_sub_to_any(team_entity)))


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
        self.assertEquals(list(entity.get_super_entities()), [])

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
        self.assertEquals(list(account_entity.get_super_entities()), [team_entity])

    def test_get_sub_entities_none(self):
        """
        Tests retrieval of sub entities when an entity has none.
        """
        # Create a team
        team = Team.objects.create()
        # Get the entity of the team
        team_entity = Entity.objects.get_for_obj(team)
        # Verify that the sub entities of the team is an empty list
        self.assertEquals(list(team_entity.get_super_entities()), [])

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
        self.assertEquals(list(team_entity.get_sub_entities()), [account_entity])

    def test_unicode(self):
        """
        Tests that the unicode method returns the display name of the entity.
        """
        account = Account.objects.create(email='hi')
        entity = Entity.objects.get_for_obj(account)
        entity_unicode = entity.__str__()
        self.assertEquals(entity_unicode, 'hi')
