from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from entity.signal_handlers import turn_on_syncing, turn_off_syncing
from entity.models import Entity, EntityKind


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
        entity_type = ContentType.objects.get_for_model(model_obj)
        return Entity.objects.create(
            entity_type=entity_type, entity_id=model_obj.id,
            entity_kind=EntityKind.objects.get_or_create(
                name='{0}__{1}'.format(entity_type.app_label, entity_type.model),
                defaults={'display_name': u'{0}'.format(entity_type)}
            )[0])
