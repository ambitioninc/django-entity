# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'EntityTag'
        db.create_table(u'entity_entitytag', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=256, db_index=True)),
            ('display_name', self.gf('django.db.models.fields.TextField')(blank=True)),
        ))
        db.send_create_signal(u'entity', ['EntityTag'])

        # Adding field 'Entity.entity_tag'
        db.add_column(u'entity_entity', 'entity_tag',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['entity.EntityTag'], null=True),
                      keep_default=False)

        # Adding unique constraint on 'Entity', fields ['entity_id', 'entity_type', 'entity_tag']
        db.create_unique(u'entity_entity', ['entity_id', 'entity_type_id', 'entity_tag_id'])


    def backwards(self, orm):
        # Removing unique constraint on 'Entity', fields ['entity_id', 'entity_type', 'entity_tag']
        db.delete_unique(u'entity_entity', ['entity_id', 'entity_type_id', 'entity_tag_id'])

        # Deleting model 'EntityTag'
        db.delete_table(u'entity_entitytag')

        # Deleting field 'Entity.entity_tag'
        db.delete_column(u'entity_entity', 'entity_tag_id')


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