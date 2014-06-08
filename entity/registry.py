from django.db.models import Model, Manager
from django.db.models.query import QuerySet

from entity.config import EntityConfig


class EntityRegistry(object):
    """
    Maintains all registered entities and provides a lookup table for models to related entities.
    """
    def __init__(self):
        # The registry of all models to their querysets and EntityConfigs
        self._registry = {}

    def register(self, model_or_qset, entity_config=None):
        """
        Registers a model or queryset with an entity config. If the entity config is None, it defaults
        to registering the mdoel/qset to EntityConfig.
        """
        if issubclass(model_or_qset, Model):
            # If the provided parameter is a model, convert it to a queryset
            model_or_qset = model_or_qset.__class__.objects

        if not issubclass(model_or_qset, (Manager, QuerySet)):
            raise ValueError('Must register a model or queryset with an entity config')

        entity_config = entity_config if entity_config is not None else EntityConfig()

        if not issubclass(entity_config, EntityConfig):
            raise ValueError('Must register entity config of subclass EntityConfig')

        self._registry[model_or_qset.model] = {
            'qset': model_or_qset,
            'entity_config': entity_config,
        }


# Define the global registry variable
registry = EntityRegistry()


def register(model_or_qset):
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
        registry.register(model_or_qset, entity_config_class)

    return _entity_config_wrapper
