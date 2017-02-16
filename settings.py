import os

from celery import Celery
from django.conf import settings


def configure_settings():
    """
    Configures settings for manage.py and for run_tests.py.
    """
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    app = Celery('entity')
    app.config_from_object('django.conf:settings')
    app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

    if not settings.configured:
        # Determine the database settings depending on if a test_db var is set in CI mode or not
        test_db = os.environ.get('DB', None)
        if test_db is None:
            db_config = {
                'ENGINE': 'django.db.backends.postgresql_psycopg2',
                'NAME': 'ambition_test',
                'USER': 'postgres',
                'PASSWORD': '',
                'HOST': 'db',
                'TEST': {
                    'CHARSET': 'UTF8',
                }
            }
        elif test_db == 'postgres':
            db_config = {
                'ENGINE': 'django.db.backends.postgresql_psycopg2',
                'USER': 'postgres',
                'NAME': 'entity',
            }
        else:
            raise RuntimeError('Unsupported test DB {0}'.format(test_db))

        installed_apps = [
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.admin',
            'celery',
            'entity',
            'entity.tests',
        ]

        settings.configure(
            TEST_RUNNER='django_nose.NoseTestSuiteRunner',
            NOSE_ARGS=['--nocapture', '--nologcapture', '--verbosity=1'],
            DATABASES={
                'default': db_config,
            },
            MIDDLEWARE_CLASSES={},
            INSTALLED_APPS=installed_apps,
            ROOT_URLCONF='entity.urls',
            DEBUG=False,
            DDF_FILL_NULLABLE_FIELDS=False,
        )
