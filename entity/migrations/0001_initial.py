# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Entity',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('display_name', models.TextField(db_index=True, blank=True)),
                ('entity_id', models.IntegerField()),
                ('entity_meta', jsonfield.fields.JSONField(null=True)),
                ('is_active', models.BooleanField(default=True, db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='EntityKind',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=256, db_index=True)),
                ('display_name', models.TextField(blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='EntityRelationship',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sub_entity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='super_relationships', to='entity.Entity')),
                ('super_entity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sub_relationships', to='entity.Entity')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='entity',
            name='entity_kind',
            field=models.ForeignKey(to='entity.EntityKind', on_delete=django.db.models.deletion.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='entity',
            name='entity_type',
            field=models.ForeignKey(to='contenttypes.ContentType', on_delete=django.db.models.deletion.PROTECT),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='entity',
            unique_together=set([('entity_id', 'entity_type', 'entity_kind')]),
        ),
    ]
