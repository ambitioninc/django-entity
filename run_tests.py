"""
Provides the ability to run test on a standalone Django app.
"""
import os
import sys
from celery import Celery
from django.conf import settings
from optparse import OptionParser


if not settings.configured:
    # Set up celery
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    app = Celery('entity')
    app.config_from_object('django.conf:settings')
    app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

    # Determine the database settings depending on if a test_db var is set in CI mode or not
    test_db = os.environ.get('DB', None)
    if test_db is None:
        db_config = {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'ambition_dev',
            'USER': 'ambition_dev',
            'PASSWORD': 'ambition_dev',
            'HOST': 'localhost'
        }
    elif test_db == 'postgres':
        db_config = {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'USER': 'postgres',
            'NAME': 'entity',
        }
    elif test_db == 'sqlite':
        db_config = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': 'entity',
        }
    else:
        raise RuntimeError('Unsupported test DB {0}'.format(test_db))

    settings.configure(
        DATABASES={
            'default': db_config,
        },
        INSTALLED_APPS=(
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.admin',
            'celery',
            'south',
            'entity',
            'entity.tests',
        ),
        ROOT_URLCONF='entity.urls',
        DDF_FILL_NULLABLE_FIELDS=False,
        DEBUG=False,
    )

from django_nose import NoseTestSuiteRunner


def run_tests(*test_args, **kwargs):
    if 'south' in settings.INSTALLED_APPS:
        from south.management.commands import patch_for_test_db_setup
        patch_for_test_db_setup()

    if not test_args:
        test_args = ['entity']

    kwargs.setdefault('interactive', False)

    test_runner = NoseTestSuiteRunner(**kwargs)

    failures = test_runner.run_tests(test_args)
    sys.exit(failures)


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('--verbosity', dest='verbosity', action='store', default=1, type=int)
    parser.add_options(NoseTestSuiteRunner.options)
    (options, args) = parser.parse_args()

    run_tests(*args, **options.__dict__)
