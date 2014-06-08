from django.db.models import Model, Manager
from django.db.models.query import QuerySet
from django.test import TestCase

from entity.config import EntityConfig
from entity.registry import registry, EntityRegistry


class EntityRegistryTest(TestCase):
    """
    Tests the EntityRegistry class.
    """
    def test_registry_is_entity_registry(self):
        """
        Tests the registry global variable is an instance of EntityRegistry.
        """
        self.assertTrue(isinstance(registry, EntityRegistry))

    def test_register_non_model_or_qset(self):
        """
        Tests that a value error is raised when trying to register something that
        isnt a model or a queryset.
        """
        class InvalidEntityObject(object):
            pass

        with self.assertRaises(ValueError):
            EntityRegistry().register(InvalidEntityObject)

    def test_register_model(self):
        """
        Tests registering a model class.
        """
        class ValidRegistryModel(Model):
            pass

        registry = EntityRegistry()
        registry.register(ValidRegistryModel)
        registry_info = registry._registry[ValidRegistryModel]
        self.assertEquals(registry_info['qset'], ValidRegistryModel.objects)
        self.assertTrue(isinstance(registry_info['entity_config'], EntityConfig))

    def test_register_inherited_model(self):
        """
        Tests registering a model class that extends an abstract model.
        """
        class BaseModel(Model):
            class Meta:
                abstract = True

        class ValidRegistryModel(BaseModel):
            pass

        registry = EntityRegistry()
        registry.register(ValidRegistryModel)
        registry_info = registry._registry[ValidRegistryModel]
        self.assertEquals(registry_info['qset'], ValidRegistryModel.objects)
        self.assertTrue(isinstance(registry_info['entity_config'], EntityConfig))

    def test_register_manager(self):
        """
        Tests registering a manager class.
        """
        class ValidRegistryManager(Manager):
            pass

        class ValidRegistryModel(Model):
            objects = ValidRegistryManager()

        registry = EntityRegistry()
        registry.register(ValidRegistryModel.objects)
        registry_info = registry._registry[ValidRegistryModel]
        self.assertEquals(registry_info['qset'], ValidRegistryModel.objects)
        self.assertTrue(isinstance(registry_info['entity_config'], EntityConfig))

    def test_register_inherited_manager(self):
        """
        Tests registering a manager class that extends another manager.
        """
        class BaseManager(Manager):
            pass

        class ValidRegistryManager(BaseManager):
            pass

        class ValidRegistryModel(Model):
            objects = ValidRegistryManager()

        registry = EntityRegistry()
        registry.register(ValidRegistryModel)
        registry_info = registry._registry[ValidRegistryModel]
        self.assertEquals(registry_info['qset'], ValidRegistryModel.objects)
        self.assertTrue(isinstance(registry_info['entity_config'], EntityConfig))

    def test_register_queryset(self):
        """
        Tests registering a queryset
        """
        class ValidRegistryManager(Manager):
            pass

        class ValidRegistryModel(Model):
            objects = ValidRegistryManager()

        registry = EntityRegistry()
        registry.register(ValidRegistryModel.objects.filter())
        registry_info = registry._registry[ValidRegistryModel]
        self.assertTrue(issubclass(registry_info['qset'].__class__, QuerySet))
        self.assertTrue(isinstance(registry_info['entity_config'], EntityConfig))
