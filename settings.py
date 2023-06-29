import os
import json

from django.conf import settings


def configure_settings():
    """
    Configures settings for manage.py and for run_tests.py.
    """
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

    if not settings.configured:
        # Determine the database settings depending on if a test_db var is set in CI mode or not
        test_db = os.environ.get('DB', None)
        if test_db is None:
            db_config = {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'entity',
                'USER': 'postgres',
                'PASSWORD': '',
                'HOST': 'db',
            }
        elif test_db == 'postgres':
            db_config = {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'entity',
                'USER': 'postgres',
                'PASSWORD': '',
                'HOST': 'db',
            }
        else:
            raise RuntimeError('Unsupported test DB {0}'.format(test_db))

        # Check env for db override (used for github actions)
        if os.environ.get('DB_SETTINGS'):
            db_config = json.loads(os.environ.get('DB_SETTINGS'))

        installed_apps = [
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.messages',
            'django.contrib.admin',
            'django.db.utils',
            'entity',
            'entity.tests',
        ]

        settings.configure(
            TEST_RUNNER='django_nose.NoseTestSuiteRunner',
            SECRET_KEY='*',
            NOSE_ARGS=['--nocapture', '--nologcapture', '--verbosity=1'],
            DATABASES={
                'default': db_config,
            },
            MIDDLEWARE=(
                'django.contrib.auth.middleware.AuthenticationMiddleware',
                'django.contrib.messages.middleware.MessageMiddleware',
                'django.contrib.sessions.middleware.SessionMiddleware'
            ),
            TEMPLATES=[{
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'APP_DIRS': True,
                'OPTIONS': {
                    'context_processors': [
                        'django.contrib.auth.context_processors.auth',
                        'django.contrib.messages.context_processors.messages',
                        'django.template.context_processors.request',
                    ]
                }
            }],
            INSTALLED_APPS=installed_apps,
            ROOT_URLCONF='entity.urls',
            DEBUG=False,
            DDF_FILL_NULLABLE_FIELDS=False,
            DEFAULT_AUTO_FIELD='django.db.models.AutoField',
        )
