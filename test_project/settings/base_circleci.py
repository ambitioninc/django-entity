import os
execfile(os.path.join(os.path.dirname(__file__), 'base.py'))


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        "NAME": "circle_test",
        "USER": "ubuntu",
        "PASSWORD": "",
    },
}
