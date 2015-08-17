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

Along with metadata, entities come with the ability to mirror a ``display_name`` field in order to provide a human-readable name for the entity that can also be filtered in the database. By default, the ``display_name`` field uses the result of the ``unicode()`` function applied to the concrete model instance. The user may override this behavior by overriding the ``get_display_name`` method in the entity configuration.

Entities can also be configured to be active or inactive, and this is done by adding an ``get_is_active`` function to the config that returns ``True`` (the default value) if the entity is active and ``False`` otherwise.

### Advanced Syncing Continued - Entity Kinds

Entities have the ability to be labeled with their "kind" for advanced filtering capabilities. The entity kind allows a user to explicitly state what type of entity is being mirrored along with providing human-readable content about the entity kind. This is done by mirroring a unique ``name`` field and a ``display_name`` field in the ``EntityKind`` object that each ``Entity`` model points to.

By default, Django Entity will mirror the content type of the entity as its kind. The name field will be the ``app_label`` of the content type followed by a dot followed by the ``model`` of the content type. For cases where this name is not descriptive enough for the kind of the entity, the user has the ability to override the ``get_entity_kind`` function in the entity config. For example:

```python
@register_entity(Account)
class AccountConfig(EntityConfig):
    def get_entity_kind(self, model_obj):
        return (model_obj.email_domain, 'Email domain {0}'.format(model_obj.email_domain))
```

In the above case, the account entities are segregated into different kinds based on the domain of the email. The second value of the returned tuple provides a human-readable version of the kind that is being created.

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
1. ``entity_kind``: The EntityKind model that describes the type of mirrored entity. Defaults to parameters related to the entity content type.
1. ``is_active``: True if the entity is active, False otherwise.

Along with these basic fields, all of the following functions can either be called directly on the ``Entity`` model or on the ``Entity`` model manager.

### Basic Model and Manager Functions
Note that since entities are activatable (i.e. can have active and inactive states), the entity model manager only accesses active entities by default. If the user wishes to access every single entity (active or inactive), they must go through the ``all_objects`` manager, which is used in the example code below. The methods below are available on the ``objects`` and ``all_objects`` model managers, although the ``active`` and ``inactive`` methods are not useful on the ``objects`` model manager since it already filters for active entities.

#### get_for_obj(model_obj)
The get_for_obj function takes a model object and returns the corresponding entity. Only available in the ``Entity`` model manager.

```python
test_model = TestModel.objects.create()
# Get the resulting entity for the model object
entity = Entity.objects.get_for_obj(test_model)
```

#### active()
Returns active entities. Only applicable when using the ``all_objects`` model manager. Note that ``objects`` already filters for only active entities.

#### inactive()
Does the opposite of ``active()``. Only applicable when using the ``all_objects`` model manager. Note that ``objects`` already disregards inactive entities.

#### is_any_kind(*entity_kinds)
Returns all entities that are any of the entity kinds provided.

#### is_not_any_kind(*entity_kinds)
The opposite of ``is_any_kind()``.

#### is_sub_to_all(*super_entities)
Return entities that are sub entities of every provided super entity (or all if no super entities are provided).

For example, if one wishes to filter all of the Account entities by the ones that belong to Group A and Group B, the code would look like this:

```python
groupa_entity = Entity.objects.get_for_obj(Group.objects.get(name='A'))
groupb_entity = Entity.objects.get_for_obj(Group.objects.get(name='B'))
for e in Entity.objects.is_sub_to_all(groupa_entity, groupb_entity):
    # Do your thing with the results
    pass
```

#### is_sub_to_any(*super_entities)
Return entities that are sub entities of any one of the provided super entities (or all if no super entities are provided).

#### is_sub_to_all_kinds(*super_entity_kinds)
Return entities for which the set of provided kinds is contained in the set of all their super-entity-kinds

#### is_sub_to_any_kind(*super_entity_kinds)
Return entities that have at least one super entity-kind contained in the provided set of kinds (or all if no kinds are provided)

#### cache_relationships()
The cache_relationships function is useful for prefetching relationship information. Accessing entities without the cache_relationships function will result in many extra database queries if filtering is performed on the entity relationships.

```python
entity = Entity.objects.cache_relationships().get_for_obj(test_model)
for super_entity in entity.get_super_entities():
    # Perform much faster accesses on super entities...
    pass
```

If one wants to ignore caching sub or super entity relationships, simply pass ``cache_sub=False`` or ``cache_super=False`` as keyword arguments to the function. Note that both of these flags are turned on by default.

### Chaining Filtering Functions
All of the manager functions listed can be chained, so it is possible to do the following combinations:

```python
Entity.objects.is_sub_to_all(groupa_entity).is_active().is_any_kind(account_kind, team_kind)

Entity.objects.inactive().is_sub_to_all(groupb_entity).cache_relationships()
```

## Arbitrary groups of Entities

Once entities and their relationships are syncing is set up, most groupings of entities will be automatically encoded with the super/sub entity relationships. However, there are occasions when the groups that are automatically encoded do not capture the full extent of groupings that are useful.

In order to support arbitrary groups of entities without requiring additional syncing code, the `EntityGroup` model is provided. This model comes with convenience functions for adding and removing entities to a group, as well as methods for querying what entities are in the arbitrary group.

In addition to adding individual entities to an EntityGroup, you can also add all of an entity's sub-entities with a given type to the `EntityGroup` very easily. The following does the following:

1. Creates an `EntityGroup`
2. Adds an individual entity to the group
3. Adds all the subentities of a given kind to the group
4. Queries for all the entities in the group

```python
my_group = EntityGroup.objects.create()

my_group.add_entity(entity=some_entity)
my_group.add_entity(entity=some_super_entity, sub_entity_kind=some_entity_kind)

all_entities_in_group = my_group.all_entities()
```

After the code above is run, `all_entities_in_group` will be a
Queryset of `Entity`s that contains the entity `some_entity` as well
as all the sub-entities of `some_super_entity` who's entity-kind is
`some_entity_kind`.

The following methods are available on `EntityGroup`s

#### all_entitites

Get a list of all individual entities in the group. This will pull out
all the entities that have been added, combining all the entities that
were added individually as well as all the entities that were added
because they are sub-entities to a super-entity that was added the the
group, with the specified entity kind.

#### add_entity

Add an individual entity, or all the sub-entities (with a given kind)
of a super-entity to the group. There are two ways to add entities to
the group with this method. The first adds an individual entity to the
group. The second adds all the individuals who are a super-entity's
sub-entities of a given kind to the group.

This allows leveraging existing groupings as well as allowing other
arbitrary additions. Both individual, and sub-entity group memberships
can be added to a single `EntityGroup`.

The syntax for adding an individual entity is as simple as specifying
the entity to add:

```python
my_group.add(some_entity)
```

And adding a sub-entity group is as simple as specifying the
super-entity and the sub-entity kind:

```python
my_group.add(entity=some_entity, sub_entity_kind=some_entity_kind)
```

#### bulk_add_entities

Add a number of entities, or sub-entity groups to the
`EntityGroup`. It takes a list of tuples, where the first item in the
tuple is an `Entity` instance, and the second is either an
`EntityKind` instance or `None`.

```python
my_group.bulk_add_entities([
    (some_entity_1, None),
    (some_entity_2, None),
    (some_super_entity_1, some_entity_kind)
    (some_super_entity_2, other_entity_kind)
])
```

#### remove_entitiy

Removes a given entity, or sub-entity grouping from the
`EntityGroup`. This method uses the same syntax of `add_entity`.

### bulk_remove_entities

Removes a number of entities or sub-entity groupings from the
`EntityGroup`. This method uses the same syntax as
`bulk_add_entities`.

#### bulk_overwrite

This method replaces all of the group members with a new set of group
members. It has the same syntax as ``bulk_add_entities``.


## Release Notes
- 1.11.0:
    - Added support for arbitrary groups of entities.
- 1.10.0:
    - Added Django 1.8 support.
- 1.9.0:
    - Updated Entity Kinds to be activatable models.
- 1.8.2:
    - Added sorting support for Entity Models in Python 3
- 1.8.0:
    - Added support for Django 1.7 and also backwards-compatible support for Django 1.6.
- 1.7.1:
    - Changed the ``is_entity_active`` function in the entity configuration to be named ``get_is_active`` for consistency with other functions.
- 1.6.0:
    - Made entities ``activatable``, i.e. they inherit the properties defined in [Django Activatable Model](https://github.com/ambitioninc/django-activatable-model)
- 1.5.0:
    - Added entity kinds to replace inadequacies of filtering by entity content types.
    - Removed is_any_type and is_not_any_type and replaced those methods with is_any_kind and is_not_any_kind in the model manager.
    - Removed chainable entity filters. All entity filtering calls are now in the model manager.

## License
MIT License (see the LICENSE file for more info).
