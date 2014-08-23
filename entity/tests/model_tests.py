from django.contrib.contenttypes.models import ContentType
from django.test.utils import override_settings
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
        self.assertEquals(set([team_entity] + account_entities), set(Entity.objects.is_any_type()))

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
        self.assertEquals([team_entity], list(Entity.objects.is_any_type(self.team_type)))
        self.assertEquals(account_entities, set(Entity.objects.is_any_type(self.account_type)))

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
            account_entities.union([team_entity]), set(Entity.objects.is_any_type(self.account_type, self.team_type)))

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
                Entity.objects.filter(id__in=(i.id for i in account_entities.union([team_entity]))).is_any_type(
                    self.account_type, self.team_type)
            ))

    def test_filter_manager_is_not_type_two(self):
        """
        Tests filtering by entity type when two types are given.
        """
        team = Team.objects.create()
        for i in range(5):
            Account.objects.create(team=team)
        self.assertEquals([], list(Entity.objects.is_not_any_type(self.team_type, self.account_type)))

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
        self.assertEquals([team_entity], list(Entity.objects.is_not_any_type(self.account_type)))
        self.assertEquals(account_entities, set(Entity.objects.is_not_any_type(self.team_type)))

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
            account_entities.union([team_entity]), set(Entity.objects.is_not_any_type()))

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
            list(Entity.objects.filter(id__in=(i.id for i in account_entities.union([team_entity]))).is_not_any_type(
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
            set(Entity.objects.all()), set(Entity.objects.is_sub_to_all()))

    def test_subset_super_entities_none_is_any_type(self):
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
            set(Entity.objects.is_sub_to_all().is_any_type(self.account_type)))

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
            set(Entity.objects.exclude(id=entities_4se[0].id).is_sub_to_all(
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
            entities = set(Entity.objects.exclude(id=entities_4se[0].id).is_sub_to_all(
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

    def test_unicode_default_missing(self):
        """
        Tests that if we can't find a better representation, we have a default __unicode__.
        """
        account = Account.objects.create()
        entity = Entity.objects.get_for_obj(account)
        entity_unicode = entity.__unicode__()
        self.assertEquals(entity_unicode, 'Entity Object')

    @override_settings(ENTITY_NAME_KEYS=('something', 'email', 'something else'))
    def test_unicode_from_settings(self):
        """
        Tests that, of the provided ENTITY_NAME_KEYS, the one that exists in entity_meta is used.
        """
        account = Account.objects.create(email="account@example.com")
        entity = Entity.objects.get_for_obj(account)
        entity_unicode = entity.__unicode__()
        self.assertEquals(entity_unicode, 'account@example.com')

    def test_unicode_null_entity_meta(self):
        """
        If entity_meta is null, __unicode__ should not fail.
        """
        account_ct = ContentType.objects.get_for_model(Account)
        e = Entity.objects.create(
            entity_id=1,
            entity_type=account_ct,
            entity_meta=None,
        )
        entity_unicode = e.__unicode__()
        self.assertEquals(entity_unicode, 'Entity Object')
