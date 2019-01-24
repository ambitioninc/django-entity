import re
from setuptools import setup, find_packages

# import multiprocessing to avoid this bug (http://bugs.python.org/issue15881#msg170215_
import multiprocessing
assert multiprocessing


def get_version():
    """
    Extracts the version number from the version.py file.
    """
    VERSION_FILE = 'entity/version.py'
    mo = re.search(r'^__version__ = [\'"]([^\'"]*)[\'"]', open(VERSION_FILE, 'rt').read(), re.M)
    if mo:
        return mo.group(1)
    else:
        raise RuntimeError('Unable to find version string in {0}.'.format(VERSION_FILE))


install_requires = [
    'Django>=1.11',
    'django-activatable-model>=1.1.0',
    'django-manager-utils>=1.3.0',
    'jsonfield>=0.9.20',
    'python3-utils>=0.3',
]

tests_require = [
    'django-dynamic-fixture',
    'django-nose>=1.4',
    'mock>=1.0.1',
    'psycopg2',
]

setup(
    name='django-entity',
    version=get_version(),
    description='Entity relationship management for Django',
    long_description=open('README.md').read(),
    url='http://github.com/ambitioninc/django-entity/',
    author='Wes Kendall',
    author_email='wesleykendall@gmail.com',
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Framework :: Django',
    ],
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require={'dev': tests_require},
    test_suite='run_tests.run_tests',
    include_package_data=True,
    zip_safe=False,
)
