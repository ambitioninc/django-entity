from django.db.models.signals import post_save, post_delete, m2m_changed
from manager_utils import post_bulk_operation

from entity.config import entity_registry
from entity.models import Entity
from entity.sync import sync_entities, sync_entities_watching


def delete_entity_signal_handler(sender, instance, **kwargs):
    """
    Defines a signal handler for syncing an individual entity. Called when
    an entity is saved or deleted.
    """
    if instance.__class__ in entity_registry.entity_registry:
        Entity.all_objects.delete_for_obj(instance)


def save_entity_signal_handler(sender, instance, **kwargs):
    """
    Defines a signal handler for saving an entity. Syncs the entity to
    the entity mirror table.
    """
    if instance.__class__ in entity_registry.entity_registry:
        sync_entities(instance)

    if instance.__class__ in entity_registry.entity_watching:
        sync_entities_watching(instance)


def m2m_changed_entity_signal_handler(sender, instance, action, **kwargs):
    """
    Defines a signal handler for a manytomany changed signal. Only listens for the
    post actions so that entities are synced once (rather than twice for a pre and post action).
    """
    if action == 'post_add' or action == 'post_remove' or action == 'post_clear':
        save_entity_signal_handler(sender, instance, **kwargs)


def bulk_operation_signal_handler(sender, *args, **kwargs):
    """
    When a bulk operation has happened on a model, sync all the entities again.
    NOTE - bulk syncing isn't turned on by default because of the consequences of it.
    For example, a user may issue a simple update to a single model, which would trigger
    syncing of all entities. It is up to the user to explicitly enable syncing on bulk
    operations with turn_on_syncing(bulk=True)
    """
    if sender in entity_registry.entity_registry:
        sync_entities()


def turn_off_syncing(for_post_save=True, for_post_delete=True, for_m2m_changed=True, for_post_bulk_operation=True):
    """
    Disables all of the signals for syncing entities. By default, everything is turned off. If the user wants
    to turn off everything but one signal, for example the post_save signal, they would do:

    turn_off_sync(for_post_save=False)
    """
    if for_post_save:
        post_save.disconnect(save_entity_signal_handler, dispatch_uid='save_entity_signal_handler')
    if for_post_delete:
        post_delete.disconnect(delete_entity_signal_handler, dispatch_uid='delete_entity_signal_handler')
    if for_m2m_changed:
        m2m_changed.disconnect(m2m_changed_entity_signal_handler, dispatch_uid='m2m_changed_entity_signal_handler')
    if for_post_bulk_operation:
        post_bulk_operation.disconnect(bulk_operation_signal_handler, dispatch_uid='bulk_operation_signal_handler')


def turn_on_syncing(for_post_save=True, for_post_delete=True, for_m2m_changed=True, for_post_bulk_operation=False):
    """
    Enables all of the signals for syncing entities. Everything is True by default, except for the post_bulk_operation
    signal. The reason for this is because when any bulk operation occurs on any mirrored entity model, it will
    result in every single entity being synced again. This is not a desired behavior by the majority of users, and
    should only be turned on explicitly.
    """
    if for_post_save:
        post_save.connect(save_entity_signal_handler, dispatch_uid='save_entity_signal_handler')
    if for_post_delete:
        post_delete.connect(delete_entity_signal_handler, dispatch_uid='delete_entity_signal_handler')
    if for_m2m_changed:
        m2m_changed.connect(m2m_changed_entity_signal_handler, dispatch_uid='m2m_changed_entity_signal_handler')
    if for_post_bulk_operation:
        post_bulk_operation.connect(bulk_operation_signal_handler, dispatch_uid='bulk_operation_signal_handler')


# Connect all default signal handlers
turn_on_syncing()
