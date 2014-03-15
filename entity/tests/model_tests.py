from django.contrib.contenttypes.models import ContentType
from entity.models import Entity

from .models import Account, Team, TeamGroup, Competitor
from .utils import EntityTestCase


class TestEntityManager(EntityTestCase):
    """
    Tests custom function in the EntityManager class.
    """
    def setUp(self):
        super(TestEntityManager, self).setUp()
        self.account_type = ContentType.objects.get_for_model(Account)
        self.team_type = ContentType.objects.get_for_model(Team)
        self.team_group_type = ContentType.objects.get_for_model(TeamGroup)
        self.competitor_type = ContentType.objects.get_for_model(Competitor)

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
            entities = Entity.objects.has_super_entity_subset(team_entity).cache_relationships()
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
        entity = Entity.objects.get_for_obj(account)
        self.assertEquals([entity], list(Entity.objects.inactive()))

    def test_filter_queryset_active(self):
        """
        Test filtering active entities from a queryset.
        """
        # Create an active and inactive account
        active_entity = Entity.objects.get_for_obj(Account.objects.create())
        inactive_entity = Entity.objects.get_for_obj(Account.objects.create(is_active=False))
        self.assertEquals(
            [active_entity], list(Entity.objects.filter(id__in=[active_entity.id, inactive_entity.id]).active()))

    def test_filter_queryset_inactive(self):
        """
        Test filtering inactive entities from a queryset.
        """
        # Create an active and inactive account
        active_entity = Entity.objects.get_for_obj(Account.objects.create())
        inactive_entity = Entity.objects.get_for_obj(Account.objects.create(is_active=False))
        self.assertEquals(
            [inactive_entity], list(Entity.objects.filter(id__in=[active_entity.id, inactive_entity.id]).inactive()))

    def test_filter_manager_is_type_none(self):
        """
        Tests filtering by entity type when no type is given.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        account_entities = [
            Entity.objects.get_for_obj(Account.objects.create(team=team))
            for i in range(5)
        ]
        self.assertEquals(set([team_entity] + account_entities), set(Entity.objects.is_type()))

    def test_filter_manager_one_type(self):
        """
        Tests filtering by entity type when one type is given.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        account_entities = set(
            Entity.objects.get_for_obj(Account.objects.create(team=team))
            for i in range(5)
        )
        self.assertEquals([team_entity], list(Entity.objects.is_type(self.team_type)))
        self.assertEquals(account_entities, set(Entity.objects.is_type(self.account_type)))

    def test_filter_manager_two_types(self):
        """
        Tests filtering by entity type when two types are given.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        account_entities = set(
            Entity.objects.get_for_obj(Account.objects.create(team=team))
            for i in range(5)
        )
        self.assertEquals(
            account_entities.union([team_entity]), set(Entity.objects.is_type(self.account_type, self.team_type)))

    def test_filter_queryset_two_types(self):
        """
        Tests filtering by entity type when two types are given on a queryset.
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
                Entity.objects.filter(id__in=(i.id for i in account_entities.union([team_entity]))).is_type(
                    self.account_type, self.team_type)
            ))

    def test_filter_manager_is_not_type_two(self):
        """
        Tests filtering by entity type when two types are given.
        """
        team = Team.objects.create()
        for i in range(5):
            Account.objects.create(team=team)
        self.assertEquals([], list(Entity.objects.is_not_type(self.team_type, self.account_type)))

    def test_filter_manager_is_not_type_one(self):
        """
        Tests filtering by entity type when one type is given.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        account_entities = set(
            Entity.objects.get_for_obj(Account.objects.create(team=team))
            for i in range(5)
        )
        self.assertEquals([team_entity], list(Entity.objects.is_not_type(self.account_type)))
        self.assertEquals(account_entities, set(Entity.objects.is_not_type(self.team_type)))

    def test_filter_manager_is_not_type_none(self):
        """
        Tests filtering by entity type when no types are given.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        account_entities = set(
            Entity.objects.get_for_obj(Account.objects.create(team=team))
            for i in range(5)
        )
        self.assertEquals(
            account_entities.union([team_entity]), set(Entity.objects.is_not_type()))

    def test_filter_queryset_two_is_not_types(self):
        """
        Tests filtering by entity type when two types are given on a queryset.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        account_entities = set(
            Entity.objects.get_for_obj(Account.objects.create(team=team))
            for i in range(5)
        )
        self.assertEquals(
            [],
            list(Entity.objects.filter(id__in=(i.id for i in account_entities.union([team_entity]))).is_not_type(
                self.account_type, self.team_type))
        )

    def test_subset_super_entities_none(self):
        """
        Tests the base case of super entity subsets on no super entities.
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
            set(Entity.objects.all()), set(Entity.objects.has_super_entity_subset()))

    def test_subset_super_entities_none_is_type(self):
        """
        Tests the base case of super entity subset on no super entities with a type specified.
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
            set(Entity.objects.has_super_entity_subset().is_type(self.account_type)))

    def test_subset_super_entities_manager(self):
        """
        Tests the subset of super entity types for an entity directly from the entity manager.
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
            entities_4se, set(Entity.objects.has_super_entity_subset(
                team_entity, team2_entity, team_group_entity, competitor_entity)))
        self.assertEquals(
            entities_1se | entities_2se2 | entities_4se, set(Entity.objects.has_super_entity_subset(team_entity)))
        self.assertEquals(
            entities_4se | entities_2se2, set(Entity.objects.has_super_entity_subset(team_entity, competitor_entity)))
        self.assertEquals(
            entities_4se | entities_2se1, set(Entity.objects.has_super_entity_subset(team_group_entity)))
        self.assertEquals(
            entities_4se | entities_2se1 | entities_2se2,
            set(Entity.objects.has_super_entity_subset(competitor_entity)))

    def test_has_super_entity_subset_queryset(self):
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
            set(Entity.objects.exclude(id=entities_4se[0].id).has_super_entity_subset(
                team_entity, team2_entity, team_group_entity, competitor_entity)))

    def test_has_super_entity_subset_queryset_num_queries(self):
        """
        Tests that super entity subset only results in one query.
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
            entities = set(Entity.objects.exclude(id=entities_4se[0].id).has_super_entity_subset(
                team_entity, team2_entity, team_group_entity, competitor_entity))

        # Test subset results
        self.assertEquals(set(entities_4se).difference([entities_4se[0]]), entities)


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
