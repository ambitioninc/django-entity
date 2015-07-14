from celery import Task

from entity.sync import sync_entities


class SyncEntitiesTask(Task):
    """
    Syncs all of the mirrored entities
    """
    def run(self, *args, **kwargs):
        # Check if there are selected model objs to update
        if 'model_obj_class' and 'model_obj_ids' in kwargs:
            sync_entities(*kwargs['model_obj_class'].objects.filter(id__in=kwargs['model_obj_ids']))
        else:
            sync_entities()
