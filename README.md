[![Build Status](https://travis-ci.org/ambitioninc/django-entity.png)](https://travis-ci.org/ambitioninc/django-entity)
Django Entity
=============
Django Entity is an app that provides Django projects with the ability to mirror their entities and entity relationships in a separate, well-contained and easily-accessible table.

Django Entity provides large-scale projects with the ability to better segregate their apps while minimizing the application-specific code in those apps that has to deal with entities and their relationships in the main project.

What is an entity? An entity is any model in your Django project. For example, an entity could be a Django User model or a Group of Users. Similarly an entity relationship defines a super and sub relationship among different types of entities. For example, a Group would be a super entity of a User. The Django Entity app allows you to easily express this relationship in your model definition and sync it to a centralized place that is accessible by any other app in your project.

## A Use Case
Imagine that you have a Django project that defines many types of groupings of your users. For example, let's say in your enterprise project, you allow users to define their manager, their company position, and their regional branch location. Similarly, let's say that you have an app that can email groups of users based on their manager (or anyone who is under the managers of that manager), their position, or their region. This email app would likely have to know application-specific modeling of these relationships in order to be built. Similarly, doing things like querying for all users under a manager hierachy can be an expensive lookup depending on how it is modeled.

Using Django Entity, the email app could be written to take an Entity model rather than having to understand the complex relationships of each group. The Entity model passed to the email app could be a CompanyPosition model, and the get_sub_entities().is_type(ContentType.objects.get_for_model(User)) would return all of the User models under that CompanyPosition model. This allows the email app to be completely segregated from how the main project defines its relationships. Similarly, the query to obtain all User models under a CompanyPosition could be much more efficient than querying directly from the project (depending on how the project has its models structured).

## How Does It Work?
In order to sync entities and their relationships from your project to the Django Entity table, you must first create a model that inherits BaseEntityModel.

```python
from entity import BaseEntityModel

class Account(BaseEntityModel):
    email = models.CharField(max_length=64)
```

When you update your models to inherit this mixin, they will automatically be synced to the Entity table when they are updated or deleted. The first time that you migrate a model in your application, you must remember to sync all of the entities so that the current ones get synced to the entity table. This can be accomplished with

```python
python manage.py sync_entities
```

Similarly, you can directly call the function to sync entities in a celery processing job or in your own application code.

```python
from entity import sync_entities

sync_entities()
```

After the entities have been synced, they can then be accessed in the primary Entity table.

```python
# Create an Account model defined from above
account = Account.objects.create(email='hello@hello.com')

# Get its entity object from the entity table using the get_for_obj function
entity = Entity.objects.get_for_obj(account)
```

## How Do I Specify Relationships And Additonal Metadata About My Entities?
Django Entity provides the ability to model relationships of your entities to other entities. It also provides further capabilities for you to store additional metadata about your entities so that it can be quickly retrieved without having to access the main project tables. Here are additional functions defined in the BaseEntityModel that allow you to model your relationships and metadata. The next section describes how to query based on these relationships and retrieve the metadata in the Entity table.

- **get_entity_meta(self)**: Return a dictionary of any JSON-serializable data. This data will be serialized into JSON and stored as a string for later access by any application. This function provides your project with the ability to save application-specific data in the metadata that can later be retrieved or viewed without having to access the main project tables. Defaults to returning None.

- **is_entity_active(self)**: Returns True if this entity is active or False otherwise. This function provides the ability to specify if a given entity in your project is active. Sometimes it is valuable to retain information about entities in your system but be able to access them in different ways based on if they are active or inactive. For example, Django's User model provides the ability to specify if the User is still active without deleting the User model. This attribute can be mirrored here in this function. Defaults to returning True.

- **get_super_entities(self)**: Returns a list of all of the models in your project that have a "super" relationship with this entity. In other words, what models in your project enclose this entity? For example, a Django User could have a Group super entity that encapsulates the current User models and any other User models in the same Group. Defaults to returning an empty list.

## Now That My Entities And Relationships Are Specified, How Do I Use It?
Let's start off with an example of two entities, an Account and a Group.

```python
from django.db import models
from entity import BaseEntityModel

class Group(BaseEntityModel):
    name = models.CharField(max_length=64)

    def get_entity_meta(self):
        """
        Save the name as metadata about the entity.
        """
        return {'name': self.name}

class Account(BaseEntityModel):
    email = models.CharField(max_length=64)
    group = models.ForeignKey(Group)
    is_active = models.BooleanField(default=True)

    def get_entity_meta(self):
        """
        Save the email and group of the Account as additional metadata.
        """
        return {
            'email': self.email,
            'group': self.group.name,
        }

    def get_super_entities(self):
        """
        The group is a super entity of the Account.
        """
        return [self.group]

    def is_entity_active(self):
        return self.is_active
```

The Account and Group entities have defined how they want their metadata mirrored along with how their relationship is set up. In this case, Accounts belong to Groups. We can create an example Account and Group and then access their mirrored metadata in the following way.

```python
group = Group.objects.create(name='Hello Group')
account = Account.objects.create(email='hello@hello.com', group=group)

# Entity syncing happens automatically behind the scenes. Grab the entity of the account and group.
# Check out their metadata.
account_entity = Entity.objects.get_for_obj(account)
print account_entity.entity_meta
{'email': 'hello@hello.com', 'group': 'Hello Group'}

group_entity = Entity.objects.get_for_obj(group)
print group_entity.entity_meta
{'name': 'Hello Group'}
```

The entity metadata can be very powerful for REST APIs and other components that wish to return data about entities within the application without actually having to query the project's tables.

Once the entities are obtained, it is also easy to query for relationships among the entities.

```python
# Print off the sub entity metadata of the group
for entity in group_entity.get_sub_entities():
    print entity.entity_meta
{'email': 'hello@hello.com', 'group': 'Hello Group'}

# Similarly, print off the super entities of the account
for entity in account_entity.get_super_entities():
    print entity.entity_meta
{'name': 'Hello Group'}

# Make the account inactive and query for active sub entities from the Group.
# It should not return anything since the account is inactive
account.is_active = False
account.save()

print len(list(group_entity.get_sub_entities().active()))
0
# The account still remains a sub entity, just an inactive one
print len(list(group_entity.get_sub_entities()))
1
```

One can also filter on the sub/super entities by their type. This is useful if the entity has many relationships of different types.

```python
for entity in group_entity.get_sub_entities().is_type(ContentType.objects.get_for_model(Account)):
    print entity.entity_meta
{'email': 'hello@hello.com', 'group': 'Hello Group'}

# Groups are not a sub entity of themselves, so this function returns nothing
print len(list(group_entity.get_sub_entities().is_type(ContentType.objects.get_for_model(Group))))
0
```

## Additional Manager and Model Filtering Methods
Django entity has additional manager methods for quick global retrieval and filtering of entities and their relationships. As shown earlier, the __active__ and __is_type__ filters can easily be applied to a list of super or sub entities. Similarly, the functions can be used at the model manager layer or the per-model level. If the functions are used at the per-model layer, they return Booleans. If used at the model manager layer, they return QuerySets. Below are the various filtering functions available in Django entity along with examples of their use. Each function notes its available at a per-model layer.

### get_for_obj(model_obj)
The get_for_obj function takes a model object and returns the corresponding entity. Only available in the Entity model manager.

```python
test_model = TestModel.objects.create()
# Get the resulting entity for the model object
entity = Entity.objects.get_for_obj(test_model)
```

### cache_relationships()
The cache_relationships function is useful for prefetching relationship information. This is especially useful when performing the various active() and is_type() filtering as shown above. Accessing entities without the cache_relationships function will result in many extra database queries if filtering is performed on the entity relationships. The cache_relationships function can be used on the model manager or a queryset. This function is only available in the Entity model manager.

```python
entity = Entity.objects.cache_relationships().get_for_obj(test_model)
for super_entity in entity.get_super_entities().active():
    # Perform much faster filtering on super entity relationships...
    pass
```

### active()
Returns only active entities. This function is available in the Entity model manager, the Entity model, and on lists of entities from the get_sub_entities or get_super_entities functions.

### inactive()
Returns only inactive entities. This function is available in the Entity model manager, the Entity model, and on lists of entities from the get_sub_entities or get_super_entities functions.

### is_type(*entity_types)
Return all entities that have one of the entity types provided. This function is available in the Entity model manager, the Entity model, and on lists of entities from the get_sub_entities or get_super_entities functions.

### is_not_type(*entity_types)
Return all entities that do not have the entity types provided. This function is available in the Entity model manager, the Entity model, and on lists of entities from the get_sub_entities or get_super_entities functions.

### has_super_entity_subset(*super_entities)
Return entities that have a subset of the given super entities. This function can be executed on the model manager, on an existing queryset, the model level, or on lists of entities from the get_sub_entities and get_super_entities functions.

For example, if one wishes to filter all of the Account entities by the ones that belong to Group A and Group B, the code would look like this:

```python
groupa_entity = Entity.objects.get_for_obj(Group.objects.get(name='A'))
groupb_entity = Entity.objects.get_for_obj(Group.objects.get(name='B'))
for e in Entity.objects.has_super_entity_subset(groupa_entity, groupb_entity):
    # Do your thing with the results
    pass
```

### Chaining Filtering Functions
All of the manager functions listed can be chained, so it is possible to do the following combinations:

```python
Entity.objects.has_super_entity_subset(groupa_entity).is_active().is_type(account_type, team_type)

Entity.objects.inactive().has_super_entity_subset(groupb_entity).cache_relationships()
```


## Caveats With Django Entity
Django Entity has some current caveats worth noting. Currently, Djagno Entity links with post_save and post_delete signals so that any BaseEntityModel will be mirrored when updated. However, if the BaseEntityModel uses other models in its metadata or in defining its relationships to other models, these will not be updated when those other models are updated. For example, if there is a GroupMembership model that defines a if a User is active within a Group, changing the GroupMembership model will not remirror the Entity tables since GroupMembership does not inherit from BaseEntityModel. Future methods will be put in place to eliminate this caveat.

Note that if a user wishes to use a custom model manager for a BaseEntityModel, the user will have to make their model manager inherit EntityModelManager. If the user does not do this, entity syncing upon bulk methods will not work properly.
