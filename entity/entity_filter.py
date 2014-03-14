from itertools import ifilter


class EntityFilter(object):
    """
    Provides chainable entity filtering capabilities on iterables of entities.
    """
    def __init__(self, entities):
        self.entities = entities

    def __iter__(self):
        """
        Returns an iterator so this object may be used with 'for' and 'in'.
        """
        return iter(self.entities)

    def active(self):
        """
        Returns relationships that have active entities.
        """
        self.entities = ifilter(lambda e: e.active(), self.entities)
        return self

    def inactive(self):
        """
        Returns relationships that have inactive entities.
        """
        self.entities = ifilter(lambda e: e.inactive(), self.entities)
        return self

    def is_type(self, *entity_types):
        """
        Returns an iterator of entities of the given entity types.
        """
        self.entities = ifilter(lambda e: e.is_type(*entity_types), self.entities)
        return self

    def is_not_type(self, *entity_types):
        """
        Returns an iterator of entities not of the given entity types.
        """
        self.entities = ifilter(lambda e: e.is_not_type(*entity_types), self.entities)
        return self

    def has_super_entity_subset(self, *super_entities):
        """
        Returns an iterator of entities that have a set of super entities that have a subset of the
        given super entities.
        """
        self.entities = ifilter(lambda e: e.has_super_entity_subset(*super_entities), self.entities)
        return self
