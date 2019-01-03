from collections import defaultdict

from django.contrib.contenttypes.models import ContentType


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

    # The queryset to fetch when syncing the entity
    queryset = None

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
        model_obj_ctype = ContentType.objects.get_for_model(self.queryset.model)
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

    def get_super_entities(self, model_objs, sync_all):
        """
        Retrieves a dictionary of entity relationships. The dictionary is keyed
        on the model class of the super entity and each value of the dictionary
        is a list of tuples. The tuples specify the ID of the sub entity and
        the ID of the super entity.

        If sync_all is True, it means all models are currently being synced
        """
        return {}


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

    def register_entity(self, entity_config):
        """
        Registers an entity config
        """
        if not issubclass(entity_config, EntityConfig):
            raise ValueError('Must register entity config class of subclass EntityConfig')

        if entity_config.queryset is None:
            raise ValueError('Entity config must define queryset')

        model = entity_config.queryset.model

        self._entity_registry[model] = entity_config()

        # Add watchers to the global look up table
        for watching_model, entity_model_getter in entity_config.watching:
            self._entity_watching[watching_model].append((model, entity_model_getter))


# Define the global registry variable
entity_registry = EntityRegistry()


def register_entity():
    """
    Registers the EntityConfig class with
    django entity:

    @register_entity()
    class AuthorConfig(EntityConfig):
        queryset = Author.objects.all()
    """
    def _entity_config_wrapper(entity_config_class):
        entity_registry.register_entity(entity_config_class)
        return entity_config_class

    return _entity_config_wrapper
