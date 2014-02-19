from setuptools import setup


setup(
    name='django-entity',
    version='0.1',
    description='Entity relationship management for Django',
    long_description='''
        Django entity provides methods and models to mirror entities and
        entity relationships in Django. Django entity provides quick access to the
        entities present in your application, their subentities, and their
        super entities.

        Given this abstration, other apps can easily plug and play into your
        hierarchical relationships in your app without the app having to
        know about the potentially complex relationships in your models.
    ''',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Framework :: Django',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.0',
        'Programming Language :: Python :: 3.1',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
    keywords='python django groups entities relationships',
    url='https://github.com/ambitioninc/django-entity',
    author='Wes Kendall',
    author_email='wesleykendall@gmail.com',
    license='MIT',
    packages=[
        'entity',
        'entity.management',
        'entity.management.commands',
    ],
    install_requires=['django>=1.6.1'],
    include_package_data=True,
    zip_safe=False,
)
