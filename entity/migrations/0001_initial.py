# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Entity'
        db.create_table(u'entity_entity', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('entity_id', self.gf('django.db.models.fields.IntegerField')()),
            ('entity_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'])),
            ('entity_meta', self.gf('jsonfield.fields.JSONField')(null=True)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal(u'entity', ['Entity'])

        # Adding model 'EntityRelationship'
        db.create_table(u'entity_entityrelationship', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('sub_entity', self.gf('django.db.models.fields.related.ForeignKey')(related_name='super_relationships', to=orm['entity.Entity'])),
            ('super_entity', self.gf('django.db.models.fields.related.ForeignKey')(related_name='sub_relationships', to=orm['entity.Entity'])),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal(u'entity', ['EntityRelationship'])


    def backwards(self, orm):
        # Deleting model 'Entity'
        db.delete_table(u'entity_entity')

        # Deleting model 'EntityRelationship'
        db.delete_table(u'entity_entityrelationship')


    models = {
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'entity.entity': {
            'Meta': {'object_name': 'Entity'},
            'entity_id': ('django.db.models.fields.IntegerField', [], {}),
            'entity_meta': ('jsonfield.fields.JSONField', [], {'null': 'True'}),
            'entity_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        u'entity.entityrelationship': {
            'Meta': {'object_name': 'EntityRelationship'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'sub_entity': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'super_relationships'", 'to': u"orm['entity.Entity']"}),
            'super_entity': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'sub_relationships'", 'to': u"orm['entity.Entity']"})
        }
    }

    complete_apps = ['entity']
