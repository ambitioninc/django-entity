from django.apps import AppConfig


class EntityConfig(AppConfig):
    name = 'entity'
    verbose_name = 'Django Entity'

    def ready(self):
        import entity.signal_handlers
        assert(entity)
