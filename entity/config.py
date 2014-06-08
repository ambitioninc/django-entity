class EntityConfig(object):
    """
    Defines the configuration for a mirrored entity.
    """
    def get_entity_meta(self):
        """
        Retrieves metadata about an entity.

        Returns:
            A dictionary of metadata about an entity or None if there is no
            metadata. Defaults to returning None
        """
        return None

    def is_entity_active(self):
        """
        Describes if the entity is currently active.

        Returns:
            A Boolean specifying if the entity is active. Defaults to
            returning True.
        """
        return True

    def get_super_entities(self):
        """
        Retrieves a list of all entities that have a "super" relationship with the
        entity.

        Returns:
            A list of models. If there are no super entities, return a empty list.
            Defaults to returning an empty list.
        """
        return []
