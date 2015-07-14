from django.test import TestCase
from django_dynamic_fixture import G
from mock import patch

from entity.models import Entity
from entity.tasks import SyncEntitiesTask


class SyncEntitiesTaskTest(TestCase):
    @patch('entity.tasks.sync_entities')
    def test_sync_entities_w_arguments(self, mock_sync_entities):
        e = G(Entity)
        SyncEntitiesTask().run(model_obj_class=Entity, model_obj_ids=[e.id])
        mock_sync_entities.assert_called_once_with(e)
