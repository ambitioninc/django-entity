# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

class Migration(DataMigration):

    def forwards(self, orm):
        for e in orm.Entity.objects.all():
            e_tag, created = orm.EntityTag.objects.get_or_create(
                name='{0}__{1}'.format(e.entity_type.app_label, e.entity_type.model), defaults={
                    'display_name': unicode(e.entity_type)
                })
            e.entity_tag = e_tag
            e.save()

    def backwards(self, orm):
        "Write your backwards methods here."

    models = {
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'entity.entity': {
            'Meta': {'unique_together': "(('entity_id', 'entity_type', 'entity_tag'),)", 'object_name': 'Entity'},
            'display_name': ('django.db.models.fields.TextField', [], {'db_index': 'True', 'blank': 'True'}),
            'entity_id': ('django.db.models.fields.IntegerField', [], {}),
            'entity_meta': ('jsonfield.fields.JSONField', [], {'null': 'True'}),
            'entity_tag': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['entity.EntityTag']", 'null': 'True'}),
            'entity_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'})
        },
        u'entity.entityrelationship': {
            'Meta': {'object_name': 'EntityRelationship'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'sub_entity': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'super_relationships'", 'to': u"orm['entity.Entity']"}),
            'super_entity': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'sub_relationships'", 'to': u"orm['entity.Entity']"})
        },
        u'entity.entitytag': {
            'Meta': {'object_name': 'EntityTag'},
            'display_name': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256', 'db_index': 'True'})
        }
    }

    complete_apps = ['entity']
    symmetrical = True
