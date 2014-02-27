from optparse import make_option

from django.core.management.base import BaseCommand

from entity.tasks import SyncEntitiesTask


class Command(BaseCommand):
    """
    A management command for syncing all entities.
    """
    option_list = BaseCommand.option_list + (
        make_option(
            '--async',
            action='store_true',
            dest='async',
            default=False,
            help='Run entity sync asynchronously'
        ),
    )

    def handle(self, *args, **options):
        """
        Runs the sync entities task synchronously or asynchronously.
        """
        if options['async']:
            SyncEntitiesTask().delay()
        else:
            SyncEntitiesTask().run()
