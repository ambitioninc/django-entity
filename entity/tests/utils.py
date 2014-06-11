from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from entity import turn_on_syncing, turn_off_syncing
from entity.models import Entity


class EntityTestCase(TestCase):
    """
    The base class for entity tests. Provides helpers for creating entities.
    """
    def setUp(self):
        """
        Ensure entity syncing is in default state when tests start.
        """
        super(EntityTestCase, self).setUp()
        turn_off_syncing()
        turn_on_syncing()

    def tearDown(self):
        """
        Make sure syncing is turned back to its original state.
        """
        super(EntityTestCase, self).tearDown()
        turn_off_syncing()
        turn_on_syncing()

    def create_entity(self, model_obj):
        """
        Given a model object, create an entity.
        """
        return Entity.objects.create(
            entity_type=ContentType.objects.get_for_model(model_obj), entity_id=model_obj.id)
