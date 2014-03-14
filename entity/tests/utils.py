from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from entity.models import Entity


class EntityTestCase(TestCase):
    """
    The base class for entity tests. Provides helpers for creating entities.
    """
    def create_entity(self, model_obj):
        """
        Given a model object, create an entity.
        """
        return Entity.objects.create(
            entity_type=ContentType.objects.get_for_model(model_obj), entity_id=model_obj.id)
