from itertools import ifilter


class EntityFilter(object):
    """
    Provides chainable entity filtering capabilities.
    """
    def __init__(self, entities):
        self.entities = entities

    def __iter__(self):
        """
        Returns an iterator so this object may be used with 'for' and 'in'.
        """
        return iter(self.entities)

    def _perform_active_filter(self, is_active):
        return ifilter(lambda e: e.is_active == is_active, self.entities)

    def active(self):
        """
        Returns relationships that have active entities.
        """
        self.entities = self._perform_active_filter(True)
        return self

    def inactive(self):
        """
        Returns relationships that have inactive entities.
        """
        self.entities = self._perform_active_filter(False)
        return self

    def is_type(self, *entity_types):
        """
        Returns a list of entities of the given entity types.
        """
        entity_type_ids = frozenset(entity_type.id for entity_type in entity_types)
        return ifilter(lambda e: e.entity_type_id in entity_type_ids, self)

    def is_not_type(self, *entity_types):
        """
        Returns a list of entities not of the given entity types.
        """
        entity_type_ids = frozenset(entity_type.id for entity_type in entity_types)
        return ifilter(lambda e: e.entity_type_id not in entity_type_ids, self)
