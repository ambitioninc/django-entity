import inspect

from django.db.models import Manager, Model
from django.db.models.query import QuerySet


class EntityConfig(object):
    """
    Defines the configuration for a mirrored entity.
    """
    def get_entity_meta(self, model_obj):
        """
        Retrieves metadata about an entity.

        Returns:
            A dictionary of metadata about an entity or None if there is no
            metadata. Defaults to returning None
        """
        return None

    def is_entity_active(self, model_obj):
        """
        Describes if the entity is currently active.

        Returns:
            A Boolean specifying if the entity is active. Defaults to
            returning True.
        """
        return True

    def get_super_entities(self, model_obj):
        """
        Retrieves a list of all entities that have a "super" relationship with the
        entity.

        Returns:
            A list of models. If there are no super entities, return a empty list.
            Defaults to returning an empty list.
        """
        return []


class EntityRegistry(object):
    """
    Maintains all registered entities and provides a lookup table for models to related entities.
    """
    def __init__(self):
        # The registry of all models to their querysets and EntityConfigs
        self._entity_registry = {}

    @property
    def entity_registry(self):
        return self._entity_registry

    def register_entity(self, model_or_qset, entity_config=None):
        """
        Registers a model or queryset with an entity config. If the entity config is None, it defaults
        to registering the mdoel/qset to EntityConfig.
        """
        if inspect.isclass(model_or_qset) and issubclass(model_or_qset, Model):
            # If the provided parameter is a model, convert it to a queryset
            model_or_qset = model_or_qset.objects

        if not issubclass(model_or_qset.__class__, (Manager, QuerySet)):
            raise ValueError('Must register a model class or queryset instance with an entity config')

        entity_config = entity_config if entity_config is not None else EntityConfig

        if not issubclass(entity_config, EntityConfig):
            raise ValueError('Must register entity config class of subclass EntityConfig')

        self._entity_registry[model_or_qset.model] = {
            'qset': model_or_qset,
            'entity_config': entity_config(),
        }


# Define the global registry variable
entity_registry = EntityRegistry()


def register_entity(model_or_qset):
    """
    Registers the given model (or queryset) class and wrapped EntityConfig class with
    django entity:

    @register(Author)
    class AuthorConfig(EntityConfig):
        pass


    The user can similarly explicitly call register with

    from django.registry import registry
    registry.register(model_or_qset, entity_config)
    """
    def _entity_config_wrapper(entity_config_class):
        entity_registry.register_entity(model_or_qset, entity_config=entity_config_class)
        return entity_config_class

    return _entity_config_wrapper
