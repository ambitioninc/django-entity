Django Entity
=============
Django entity is an app that provides Django projects with the ability to mirror their entities and entity relationships in a separate, well-contained and easily-accessible table.

Django entity provides large-scale projects with the ability to better segregate their apps while minimizing the application-specific code in those apps that has to deal with entities and their relationships in the main project.

What is an entity? An entity is any model in your Django project. For example, an entity could be a Django User model or a Group of Users. Similarly an entity relationship defines a super and sub relationship among different types of entities. For example, a Group would be a super entity of a User. The Django entity app allows you to easily express this relationship in your model definition and sync it to a centralized place that is accessible by any other app in your project.

## A Use Case
Imagine that you have a Django project that defines many types of groupings of your users. For example, let's say in your enterprise project, you allow users to define their manager, their company position, and their regional branch location. Similarly, let's say that you have an app that can email groups of users based on their manager (or anyone who is under the managers of that manager), their position, or their region. This email app would likely have to know application-specific modeling of these relationships in order to be built. Similarly, doing things like querying for all users undera manager hierachy can be an expensive lookup depending on how it is modeled.

Using Djagoo entity, the email app could be written to take an Entity model rather than having to understand the complex relationships of each group. The Entity model passed to the email app could be a CompanyPosition model, and the get_sub_entities(entity_type=ContentType.objects.get_for_model(User)) would return all of the User models under that CompanyPosition model. This allows the email app to be completely segregated from how the main project defines its relationships. Similarly, the query to obtain all User models under a CompanyPosition could be much more efficient than querying directly from the project (depending on how the project has its models structured).

## How Does It Work?
In order to sync entities and their relationships from your project to the Django entity table, you must first create a model that inherits DjangoEntityMixin.

    from django.db import models
    from entity import EntityModelMixin

    class Account(models.Model, EntityModelMixin):
        email = models.CharField(max_length=64)

When you update your models to inherit this mixin, they will automatically be synced to the Entity table when they are updated or deleted. The first time that you migrate a model in your application, you must remember to sync all of the entities so that the current ones get synced to the entity table. This can be accomplished with

    python manage.py sync_entities

Similarly, you can directly call the function to sync entities in a celery processing job or in your own application code.

    from entity import sync_entities

    sync_entities()

After the entities have been synced, they can then be accessed in the primary Entity table.

    # Create an Account model defined from above
    account = Account.objects.create(email='hello@hello.com')

    # Get its entity object from the entity table
    entity = Entity.objects.get(entity_type=ContentType.objects.get_for_model(Account), entity_id=account.id)

## How Do I Specify Relationships and Additonal Metadata about My Entities?
Django entity provides the ability to model relationships of your entities to other entities. It also provides further capabilities for you to store additional metadata about your entities so that it can be quickly retrieved without having to access the main project tables. Here are additional functions defined in the EntityModelMixin that allow you to model your relationships and metadata. The next section describes how to query based on these relationships and retrieve the metadata in the Entity table.

- get_entity_meta(self): Return a dictionary of any JSON-serializable data. This data will be serialized into JSON and stored as a string for later access by any application. This function provides your project with the ability to save application-specific data in the metadata that can later be retrieved or viewed without having to access the main project tables. Defaults to returning None.

- is_entity_active(self): Returns True if this entity is active or False otherwise. This function provides the ability to specify if a given entity in your project is active. Sometimes it is valuable to retain information about entities in your system but be able to access them in different ways based on if they are active or inactive. For example, Django's User model provides the ability to specify if the User is still active without deleting the User model. This attribute can be mirrored here in this function. Defaults to returning True.

- get_super_entities(self): Returns a list of all of the models in your project that have a "super" relationship with this entity. In other words, what models in your project enclose this entity? For example, a Django User could have a Group super entity that encapsulates the current User models and any other User models in the same Group. Defaults to returning an empty list.

- is_super_entity_relationship_active(self, super_entity_model_obj): Returns True if the entity has an active relationship with the given super entity model object. Similar to how entities can be active or inactive, their relationships to super entities can be active or inactive. This allows entities to still belong to a larger super entity, but be excluded from queries to the relationships of entities. For example, a User of a Group may be temporarily banned from the Group, but the User's Group relationship may still be important for other things. This function defaults to returning True.
