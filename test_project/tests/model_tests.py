from django.contrib.contenttypes.models import ContentType
from entity.models import Entity

from test_project.models import Account, Team, TeamGroup, Competitor
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

    def test_manager_cached_relationships(self):
        """
        Tests a retrieval of cached relationships on the manager and verifies it results in the smallest amount of
        queries
        """
        team = Team.objects.create()
        for i in range(5):
            Account.objects.create(team=team)

        # Five queries should happen here - one for all entities, two for EntityRelationships,
        # and two more for entities in the relationships
        with self.assertNumQueries(5):
            entities = Entity.objects.cached_relationships()
            for entity in entities:
                self.assertTrue(len(list(entity.get_super_entities())) >= 0)
                self.assertTrue(len(list(entity.get_sub_entities())) >= 0)
        self.assertEquals(entities.count(), 6)

    def test_queryset_cached_relationships(self):
        """
        Tests a retrieval of cached relationships on the queryset and verifies it results in the smallest amount of
        queries
        """
        team = Team.objects.create()
        for i in range(5):
            Account.objects.create(team=team)

        entity_ids = [i.id for i in Entity.objects.all()]
        # Five queries should happen here - 1 for the Entity filter, two for EntityRelationships, and two more
        # for entities in those relationships
        with self.assertNumQueries(5):
            entities = Entity.objects.filter(id__in=entity_ids).cached_relationships()
            for entity in entities:
                self.assertTrue(len(list(entity.get_super_entities())) >= 0)
                self.assertTrue(len(list(entity.get_sub_entities())) >= 0)
        self.assertEquals(entities.count(), 6)

    def test_cached_intersection(self):
        """
        Tests that caching still operates the same on an intersection.
        """
        team = Team.objects.create()
        team_entity = Entity.objects.get_for_obj(team)
        for i in range(5):
            Account.objects.create(team=team)

        # Five queries should happen here - 1 for the Entity filter, two for EntityRelationships, and one more
        # for entities in those relationships (since no sub relationships exist)
        with self.assertNumQueries(4):
            entities = Entity.objects.intersect_super_entities(team_entity).cached_relationships()
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

    def test_intersect_super_entities_none(self):
        """
        Tests the base case of intersection on no super entities.
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
        for i in range(5):
            Account.objects.create(competitor=competitor, team=team, team2=team2, team_group=team_group)

        # Create accounts that have no super entities
        entities_0se = set(Entity.objects.get_for_obj(Account.objects.create()) for i in range(5))

        self.assertEquals(
            set(entities_0se).union([team_entity, team2_entity, team_group_entity, competitor_entity]),
            set(Entity.objects.intersect_super_entities()))

    def test_intersect_super_entities_manager(self):
        """
        Tests the intersection of super entity types for an entity directly from the entity manager.
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

        # Test various intersection results
        self.assertEquals(
            entities_4se, set(Entity.objects.intersect_super_entities(
                team_entity, team2_entity, team_group_entity, competitor_entity)))
        self.assertEquals(
            entities_1se | entities_2se2 | entities_4se, set(Entity.objects.intersect_super_entities(team_entity)))
        self.assertEquals(
            entities_4se | entities_2se2, set(Entity.objects.intersect_super_entities(team_entity, competitor_entity)))
        self.assertEquals(
            entities_4se | entities_2se1, set(Entity.objects.intersect_super_entities(team_group_entity)))
        self.assertEquals(
            entities_4se | entities_2se1 | entities_2se2,
            set(Entity.objects.intersect_super_entities(competitor_entity)))

    def test_intersect_super_entities_queryset(self):
        """
        Tests the intersection of super entity types for an entity from a queryset.
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

        # Test intersection results
        self.assertEquals(
            set(entities_4se).difference([entities_4se[0]]),
            set(Entity.objects.exclude(id=entities_4se[0].id).intersect_super_entities(
                team_entity, team2_entity, team_group_entity, competitor_entity)))

    def test_intersect_super_entities_queryset_num_queries(self):
        """
        Tests that super entity intersection only results in one query.
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
            entities = set(Entity.objects.exclude(id=entities_4se[0].id).intersect_super_entities(
                team_entity, team2_entity, team_group_entity, competitor_entity))

        # Test intersection results
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
