from collections import defaultdict
import inspect

from django.contrib.contenttypes.models import ContentType
from django.db.models import Manager, Model
from django.db.models.query import QuerySet


class EntityConfig(object):
    """
    Defines the configuration for a mirrored entity.
    """
    # The "watching" class variable is a list of tuples that specify what models this entity
    # config watches and the function to extract entity models from the watching model. The
    # function's return must be an iterable object.
    #
    # For example, assume we have an Account model that has a foreign key to a User
    # model. Also, the User model has a M2M to Groups. If Groups are a super entity
    # of an Account, the user must set up a watching variable so that the account
    # is synced when the M2M on the user object is changed. This is because the
    # M2M is not directly on the Account model and does not trigger Account syncing
    # by default when changed. The watching variable would look like the following:
    #
    #     watching = [
    #         (User, lambda user_model_obj: Account.objects.filter(user=user_model_obj))
    #     ]
    #
    watching = []

    def get_display_name(self, model_obj):
        """
        Returns a human-readable string for the entity.
        """
        return u'{0}'.format(model_obj)

    def get_entity_kind(self, model_obj):
        """
        Returns a tuple for a kind name and kind display name of an entity.
        By default, uses the app_label and model of the model object's content
        type as the kind.
        """
        model_obj_ctype = ContentType.objects.get_for_model(model_obj)
        return (u'{0}.{1}'.format(model_obj_ctype.app_label, model_obj_ctype.model), u'{0}'.format(model_obj_ctype))

    def get_entity_meta(self, model_obj):
        """
        Retrieves metadata about an entity.

        Returns:
            A dictionary of metadata about an entity or None if there is no
            metadata. Defaults to returning None
        """
        return None

    def get_is_active(self, model_obj):
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

        # Stores a list of (model, qset_arg) tuples for each watching model
        self._entity_watching = defaultdict(list)

    @property
    def entity_registry(self):
        return self._entity_registry

    @property
    def entity_watching(self):
        return self._entity_watching

    def register_entity(self, model_or_qset, entity_config=None):
        """
        Registers a model or queryset with an entity config. If the entity config is None, it defaults
        to registering the model/qset to EntityConfig.
        """
        if inspect.isclass(model_or_qset) and issubclass(model_or_qset, Model):
            # If the provided parameter is a model, convert it to a queryset
            model = model_or_qset
            qset = None
        elif issubclass(model_or_qset.__class__, (Manager, QuerySet)):
            model = model_or_qset.model
            qset = model_or_qset.all()
        else:
            raise ValueError('Must register a model class or queryset instance with an entity config')

        entity_config = entity_config if entity_config is not None else EntityConfig
        if not issubclass(entity_config, EntityConfig):
            raise ValueError('Must register entity config class of subclass EntityConfig')

        if model not in self._entity_registry:
            self._entity_registry[model] = (qset, entity_config())

            # Add watchers to the global look up table
            for watching_model, entity_model_getter in entity_config.watching:
                self._entity_watching[watching_model].append((model, entity_model_getter))


# Define the global registry variable
entity_registry = EntityRegistry()


def register_entity(model_or_qset):
    """
    Registers the given model (or queryset) class and wrapped EntityConfig class with
    django entity:

    @register_entity(Author)
    class AuthorConfig(EntityConfig):
        pass


    The user can similarly explicitly call register with

    from django.registry import registry
    entity_registry.register_entity(model_or_qset, entity_config)
    """
    def _entity_config_wrapper(entity_config_class):
        entity_registry.register_entity(model_or_qset, entity_config=entity_config_class)
        return entity_config_class

    return _entity_config_wrapper
