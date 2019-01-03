from django.db.models import Model
from django.test import TestCase
from mock import patch

from entity.config import EntityConfig, entity_registry, EntityRegistry, register_entity


class EntityRegistryTest(TestCase):
    """
    Tests the EntityRegistry class.
    """
    def test_entity_registry_is_instance_entity_registry(self):
        """
        Tests the entity_registry global variable is an instance of EntityRegistry.
        """
        self.assertTrue(isinstance(entity_registry, EntityRegistry))

    def test_register_non_model_or_qset(self):
        """
        Tests that a value error is raised when trying to register something that
        isnt a model or a queryset.
        """
        class InvalidEntityObject(object):
            pass

        with self.assertRaises(ValueError):
            EntityRegistry().register_entity(InvalidEntityObject)

    def test_register_valid_entity_config(self):
        """
        Tests registering an entity config with a model.
        """
        class ValidRegistryModel(Model):
            pass

        class ValidEntityConfig(EntityConfig):
            queryset = ValidRegistryModel.objects.all()

        entity_registry = EntityRegistry()
        entity_registry.register_entity(ValidEntityConfig)
        entity_registry_info = entity_registry._entity_registry[ValidRegistryModel]
        self.assertTrue(isinstance(entity_registry_info, ValidEntityConfig))

    def test_register_invalid_entity_config(self):
        """
        Tests registering an invalid entity config that does not inherit EntityConfig
        """
        class ValidRegistryModel(Model):
            pass

        class InvalidEntityConfig(object):
            pass

        entity_registry = EntityRegistry()
        with self.assertRaises(ValueError):
            entity_registry.register_entity(InvalidEntityConfig)

    def test_register_invalid_entity_config_no_qset(self):
        """
        Tests registering an invalid entity config that does not have queryset
        """
        class ValidRegistryModel(Model):
            pass

        class InvalidEntityConfig(EntityConfig):
            pass

        entity_registry = EntityRegistry()
        with self.assertRaises(ValueError):
            entity_registry.register_entity(InvalidEntityConfig)

    @patch.object(EntityRegistry, 'register_entity')
    def test_decorator(self, register_mock):
        """
        Tests the decorator calls appropriate functions.
        """
        class ValidRegistryModel(Model):
            pass

        @register_entity()
        class ValidEntityConfig(EntityConfig):
            queryset = ValidRegistryModel.objects.all()

        register_mock.assert_called_once_with(ValidEntityConfig)

    @patch.object(EntityRegistry, 'register_entity')
    def test_decorator_qset(self, register_mock):
        """
        Tests the decorator calls appropriate functions.
        """
        class ValidRegistryModel(Model):
            pass

        @register_entity()
        class ValidEntityConfig(EntityConfig):
            queryset = ValidRegistryModel.objects.all()

        register_mock.assert_called_once_with(ValidEntityConfig)
