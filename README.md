[![Build Status](https://travis-ci.org/ambitioninc/django-entity.png)](https://travis-ci.org/ambitioninc/django-entity)
Django Entity
=============
Django Entity is an app that provides Django projects with the ability to mirror their entities and entity relationships in a separate, well-contained and easily-accessible table.

Django Entity provides large-scale projects with the ability to better segregate their apps while minimizing the application-specific code in those apps that has to deal with entities and their relationships in the main project.

What is an entity? An entity is any model in your Django project. For example, an entity could be a Django User model or a Group of Users. Similarly, an entity relationship defines a super and sub relationship among different types of entities. For example, a Group would be a super entity of a User. The Django Entity app allows you to easily express this relationship in your model definition and sync it to a centralized place that is accessible by any other app in your project.

## A Use Case
Imagine that you have a Django project that defines many types of groupings of your users. For example, let's say in your enterprise project, you allow users to define their manager, their company position, and their regional branch location. Similarly, let's say that you have an app that can email groups of users based on their manager (or anyone who is under the managers of that manager), their position, or their region. This email app would likely have to know application-specific modeling of these relationships in order to be built. Similarly, doing things like querying for all users under a manager hierachy can be an expensive lookup depending on how it is modeled.

Using Django Entity, the email app could be written to take an Entity model rather than having to understand the complex relationships of each group. The Entity model passed to the email app could be a CompanyPosition model, and the get_sub_entities().is_any_type(ContentType.objects.get_for_model(User)) would return all of the User models under that CompanyPosition model. This allows the email app to be completely segregated from how the main project defines its relationships. Similarly, the query to obtain all User models under a CompanyPosition could be much more efficient than querying directly from the project (depending on how the project has its models structured).

## Getting Started - Configuring Entity Syncing
### Basic Use Case
Similar to Django's model admin, entities are configured by registering them with the Entity registry as follows:

```python
from entity import entity_registry

class Account(Model):
    email = models.CharField(max_length=64)

entity_registry.register_entity(Account)
```

And just like that, the ``Account`` model is now synced to the ``Entity`` table every time an account is saved, deleted, or has any of its M2M fields updated.

### More Advanced Syncing Options
Django Entity would not be much if it only synced objects to a single ``Entity`` table. In order to take advantage of the power of mirroring relationships, the user must define a configuration for the entity that inherits ``EntityConfig``. A small example of this is below and extends our account model to have a ``Group`` foreign key.

```python
from entity import register_entity, EntityConfig, entity_registry

class Account(Model):
    email = models.CharField(max_length=64)
    group = models.ForeignKey(Group)

entity_registry.register_entity(Group)

@register_entity(Account)
class AccountConfig(EntityConfig):
    def get_super_entities(self, model_obj):
        return [model_obj.group]
```

In the above scenario, we mirrored the ``Group`` model using the default entity configuration. However, the ``Account`` model now uses a special configuration that inherits ``EntityConfig``. It overrides the ``get_super_entities`` function to return a list of all model objects that are super entities to the account. Once the account is synced, the user may then do various filtering on the relationships of accounts to groups (more on that later).

Note - in the above example, we also used the ``register_entity`` decorator, which is really just short notation for doing ``entity_registry.register_entity(model_class, entity_config_class)``.

Along with the ability to mirror relationships, the entity configuration can be extended to mirror metadata about an entity. For example, using the ``Account`` model in the previous example:

```python
@register_entity(Account)
class AccountConfig(EntityConfig):
    def get_super_entities(self, model_obj):
        return [model_obj.group]

    def get_entity_meta(self, model_obj):
        return {
            'email': model_obj.email
        }
```

With the above configuration, every account entity will have an entity_meta field (a JSON field) that has the email attribute mirrored as well. The metadata mirroring can be powerful for building generic apps on top of entities that need access to concrete fields of a concrete model (without having to prefetch all of the concrete models pointed to by the entities).

Entities can also be configured to be active or inactive, and this is done by adding an ``is_entity_active`` function to the config that returns ``True`` (the default value) if the entity is active and ``False`` otherwise.

### Even More Advanced Syncing - Watching Other Models

Underneath the hood, Django Entity is syncing up the mirrored Entity table when saves, deletes, and M2M updates are happening on the mirrored models. However, some models may actually depend on objects that are not pointed to by the immediate fields of the model. For example, assume that we have the following models:

```python
class Group(models.Model):
    group_name = models.CharField()


class User(models.Model):
    email = models.CharField()
    groups = models.ManyToManyField(Group)


class Account(models.Model):
    user = models.OneToOneField(User)
```

Now, assume that the ``Account`` model wants to add every ``Group`` model in the many to many of the ``User`` model as its super entity. This would be set up with the following config:

```python
entity_registry.register_entity(Group)

@register_entity(Account):
class AccountConfig(EntityConfig):
    def get_super_entities(self, model_obj):
        return model_obj.user.groups.all()
```

Although it would be nice if this worked out of the box, Django Entity has no way of knowing that the ``Account`` model needs to be updated when the fields in its associated ``User`` model change. In order to ensure the ``Account`` model is mirrored properly, add a ``watching`` class variable to the entity config as follows:

```python
entity_registry.register_entity(Group)

@register_entity(Account):
class AccountConfig(EntityConfig):
    watching = [
        (User, lambda user_obj: Account.objects.filter(user=user_obj)),
    ]

    def get_super_entities(self, model_obj):
        return model_obj.user.groups.all()
```

The ``watching`` field defines a list of tuples. The first element in each tuple represents the model to watch. The second element in the tuple describes the function used to access the entity models that are related to the changed watching model.

Here's another more complex example using an ``Address`` model that points to an account.:

```python
class Address(models.Model):
    account = models.ForeignKey(Account)
```

To make the Address model sync when the ``User`` model of the ``Account`` model is changed, define an entity configuration like so:

```python
@register_entity(Address):
class AddressConfig(EntityConfig):
    watching = [
        (User, lambda user_model_obj: Address.objects.fitler(account__user=user_model_obj)),
    ]
```

Again, all that is happening under the hood is that when a ``User`` model is changed, all entity models related to that changed user model are returned so that they can be sycned.

### Ensuring Entity Syncing Optimal Queries
Since a user may need to mirror many different super entities from many different foreign keys, it is beneficial for them to provide caching hints to Django Entity. This can be done by simply providing a Django QuerySet as an argument when registering entities rather than a model class. For example, our previous account entity config would want to do the following:

```python
@register_entity(Account.objects.prefetch_related('user__groups'))
class AccountConfig(EntityConfig):
    ...
```

When invididual entities or all entities are synced, the QuerySet will be used to access the ``Account`` models.


## Syncing Entities
Models will be synced automatically when they are configured and registered with Django entity. However, the user will need to sync all entities initially after configuring the entities (and also subsequently resync all when configuration changes occur). This can be done with the sync_entities management command:

```python
# Sync all entities
python manage.py sync_entities
```

Similarly, you can directly call the function to sync entities in a celery processing job or in your own application code.

```python
from entity import sync_entities

# Sync all entities
sync_entities()
```

Note that the ``sync_entities()`` function takes a variable length list of model objects if the user wishes to sync individual entities:

```python
from entity import sync_entities

# Sync three specific models
sync_entities(account_model_obj, group_model_obj, another_model_obj)
```

Entity syncing can be costly depending on the amount of relationships mirrored. If the user is going to be updating many models in a row that are mirrored as entities, it is recommended to turn syncing off, explicitly sync all updated entities, and then turn syncing back on. This can be accomplished as follows:

```python
from entity import turn_on_syncing, turn_off_syncing, sync_entities


# Turn off syncing since we're going to be updating many different accounts
turn_off_syncing()

# Update all of the accounts
accounts_to_update = [list of accounts]
for account in accounts_to_update:
    account.update(...)

# Explicitly sync the entities updated to keep the mirrored entities up to date
sync_entities(*accounts_to_update)

# Dont forget to turn syncing back on...
turn_on_syncing()
```

## Accessing Entities
After the entities have been synced, they can then be accessed in the primary entity table. The ``Entity`` model has the following fields:

1. ``entity_type``: The ``ContentType`` of the mirrored entity.
1. ``entity_id``: The object ID of the mirrored entity.
1. ``entity_meta``: A JSONField of mirrored metadata about an entity (or null or none mirrored).
1. ``is_active``: True if the entity is active, False otherwise.

Along with these basic fields, all of the following functions can either be called directly on the ``Entity`` model or on the ``Entity`` model manager.

### Basic Model and Manager Functions
#### get_for_obj(model_obj)
The get_for_obj function takes a model object and returns the corresponding entity. Only available in the ``Entity`` model manager.

```python
test_model = TestModel.objects.create()
# Get the resulting entity for the model object
entity = Entity.objects.get_for_obj(test_model)
```

#### active()
Returns active entities when called on the ``Entity`` manager, or a boolean when called on an ``Entity`` object.

#### inactive()
Does the opposite of ``active()``.

#### is_any_type(*entity_types)
If called on the ``Entity`` manager, returns all entities that have any of the entity types provided. Returns a boolean if called on the ``Entity`` model.

#### is_not_any_type(*entity_types)
The opposite of ``is_any_type()``.

#### is_sub_to_all(*super_entities)
Return entities that are sub entities of every provided super entity (or all if no super entities are provided). This function can be executed on the model manager, on an existing queryset, the model level, or on lists of entities from the get_sub_entities and get_super_entities functions.

For example, if one wishes to filter all of the Account entities by the ones that belong to Group A and Group B, the code would look like this:

```python
groupa_entity = Entity.objects.get_for_obj(Group.objects.get(name='A'))
groupb_entity = Entity.objects.get_for_obj(Group.objects.get(name='B'))
for e in Entity.objects.is_sub_to_all(groupa_entity, groupb_entity):
    # Do your thing with the results
    pass
```

#### cache_relationships()
The cache_relationships function is useful for prefetching relationship information. This is especially useful when performing the various active() and is_any_type() filtering as shown above. Accessing entities without the cache_relationships function will result in many extra database queries if filtering is performed on the entity relationships. The cache_relationships function can be used on the model manager or a queryset.

```python
entity = Entity.objects.cache_relationships().get_for_obj(test_model)
for super_entity in entity.get_super_entities().active():
    # Perform much faster filtering on super entity relationships...
    pass
```

### Chaining Filtering Functions
All of the manager functions listed can be chained, so it is possible to do the following combinations:

```python
Entity.objects.is_sub_to_all(groupa_entity).is_active().is_any_type(account_type, team_type)

Entity.objects.inactive().is_sub_to_all(groupb_entity).cache_relationships()
```

## A Final Word
As a project increases in size and complexity, abstractions on top of project-specific models are important to the longevity of the code. It is even more important for the apps that are built around the project. Django Entity provides a powerful abstraction in this regard. If you have any comments, issues, or suggestions for the project, feel free to make issues here on Github or contact us at opensource@ambition.com.

## License
MIT License (see the LICENSE file for more info).
