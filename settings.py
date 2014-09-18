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
            DEBUG=False,
            DDF_FILL_NULLABLE_FIELDS=False,
            NOSE_ARGS=['--nocapture', '--nologcapture', '--verbosity=1'],
        )
