from django.db.models import Model, Manager
from django.db.models.query import QuerySet
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

    def test_register_model(self):
        """
        Tests registering a model class.
        """
        class ValidRegistryModel(Model):
            pass

        entity_registry = EntityRegistry()
        entity_registry.register_entity(ValidRegistryModel)
        entity_registry_info = entity_registry._entity_registry[ValidRegistryModel]
        self.assertEquals(entity_registry_info[0], None)
        self.assertTrue(isinstance(entity_registry_info[1], EntityConfig))

    def test_register_twice(self):
        """
        Tests that registering a model twice causes no harm.
        """
        class ValidRegistryModel(Model):
            pass

        entity_registry = EntityRegistry()
        entity_registry.register_entity(ValidRegistryModel)
        entity_registry.register_entity(ValidRegistryModel)
        entity_registry_info = entity_registry._entity_registry[ValidRegistryModel]
        self.assertEquals(entity_registry_info[0], None)
        self.assertTrue(isinstance(entity_registry_info[1], EntityConfig))

    def test_register_inherited_model(self):
        """
        Tests registering a model class that extends an abstract model.
        """
        class BaseModel(Model):
            class Meta:
                abstract = True

        class ValidRegistryModel(BaseModel):
            pass

        entity_registry = EntityRegistry()
        entity_registry.register_entity(ValidRegistryModel)
        entity_registry_info = entity_registry._entity_registry[ValidRegistryModel]
        self.assertEquals(entity_registry_info[0], None)
        self.assertTrue(isinstance(entity_registry_info[1], EntityConfig))

    def test_register_manager(self):
        """
        Tests registering a manager class.
        """
        class ValidRegistryManager(Manager):
            pass

        class ValidRegistryModel(Model):
            objects = ValidRegistryManager()

        entity_registry = EntityRegistry()
        entity_registry.register_entity(ValidRegistryModel.objects)
        entity_registry_info = entity_registry._entity_registry[ValidRegistryModel]
        self.assertTrue(isinstance(entity_registry_info[0], QuerySet))
        self.assertEquals(entity_registry_info[0].model, ValidRegistryModel)
        self.assertTrue(isinstance(entity_registry_info[1], EntityConfig))

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

        entity_registry = EntityRegistry()
        entity_registry.register_entity(ValidRegistryModel.objects)
        entity_registry_info = entity_registry._entity_registry[ValidRegistryModel]
        self.assertTrue(isinstance(entity_registry_info[0], QuerySet))
        self.assertTrue(isinstance(entity_registry_info[1], EntityConfig))

    def test_register_valid_entity_config(self):
        """
        Tests registering an entity config with a model.
        """
        class ValidRegistryModel(Model):
            pass

        class ValidEntityConfig(EntityConfig):
            pass

        entity_registry = EntityRegistry()
        entity_registry.register_entity(ValidRegistryModel, ValidEntityConfig)
        entity_registry_info = entity_registry._entity_registry[ValidRegistryModel]
        self.assertEquals(entity_registry_info[0], None)
        self.assertTrue(isinstance(entity_registry_info[1], ValidEntityConfig))

    def test_register_invalid_entity_config(self):
        """
        Tests registering an invalid entity config with a model.
        """
        class ValidRegistryModel(Model):
            pass

        class InvalidEntityConfig(object):
            pass

        entity_registry = EntityRegistry()
        with self.assertRaises(ValueError):
            entity_registry.register_entity(ValidRegistryModel, InvalidEntityConfig)

    @patch.object(EntityRegistry, 'register_entity', spec_set=True)
    def test_decorator(self, register_mock):
        """
        Tests the decorator calls appropriate functions.
        """
        class ValidRegistryModel(Model):
            pass

        @register_entity(ValidRegistryModel)
        class ValidEntityConfig(EntityConfig):
            pass

        register_mock.assert_called_once_with(ValidRegistryModel, entity_config=ValidEntityConfig)

    @patch.object(EntityRegistry, 'register_entity', spec_set=True)
    def test_decorator_qset(self, register_mock):
        """
        Tests the decorator calls appropriate functions.
        """
        class ValidRegistryModel(Model):
            pass

        qset = ValidRegistryModel.objects.filter()

        @register_entity(qset)
        class ValidEntityConfig(EntityConfig):
            pass

        register_mock.assert_called_once_with(qset, entity_config=ValidEntityConfig)
