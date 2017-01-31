from django.core.management.base import BaseCommand

from entity.sync import sync_entities


class Command(BaseCommand):
    """
    A management command for syncing all entities.
    """

    def handle(self, *args, **options):
        """
        Runs sync entities
        """
        sync_entities()
