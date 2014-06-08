from django.db.models import Model, Manager
from django.test import TestCase
from mock import patch

from entity.config import EntityConfig
from entity.registry import registry, EntityRegistry, register


class EntityRegistryTest(TestCase):
    """
    Tests the EntityRegistry class.
    """
    def test_contains_false(self):
        """
        Tests __contains__ when it returns False
        """
        r = EntityRegistry()
        self.assertFalse('invalid' in r)

    def test_contains_true(self):
        """
        Tests __contains__ when it returns True
        """
        r = EntityRegistry()
        r._registry['valid'] = True
        self.assertTrue('valid' in r)

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

    def test_register_valid_entity_config(self):
        """
        Tests registering an entity config with a model.
        """
        class ValidRegistryModel(Model):
            pass

        class ValidEntityConfig(EntityConfig):
            pass

        registry = EntityRegistry()
        registry.register(ValidRegistryModel, ValidEntityConfig)
        registry_info = registry._registry[ValidRegistryModel]
        self.assertEquals(registry_info['qset'], ValidRegistryModel.objects)
        self.assertTrue(isinstance(registry_info['entity_config'], ValidEntityConfig))

    @patch.object(EntityRegistry, 'register', spec_set=True)
    def test_decorator(self, register_mock):
        """
        Tests the decorator calls appropriate functions.
        """
        class ValidRegistryModel(Model):
            pass

        @register(ValidRegistryModel)
        class ValidEntityConfig(EntityConfig):
            pass

        register_mock.assert_called_once_with(ValidRegistryModel, entity_config=ValidEntityConfig)

    @patch.object(EntityRegistry, 'register', spec_set=True)
    def test_decorator_qset(self, register_mock):
        """
        Tests the decorator calls appropriate functions.
        """
        class ValidRegistryModel(Model):
            pass

        qset = ValidRegistryModel.objects.filter()

        @register(qset)
        class ValidEntityConfig(EntityConfig):
            pass

        register_mock.assert_called_once_with(qset, entity_config=ValidEntityConfig)
