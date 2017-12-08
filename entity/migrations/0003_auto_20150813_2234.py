# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('entity', '0002_entitykind_is_active'),
    ]

    operations = [
        migrations.CreateModel(
            name='EntityGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='EntityGroupMembership',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('entity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='entity.Entity')),
                ('entity_group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='entity.EntityGroup')),
                ('sub_entity_kind', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='entity.EntityKind', null=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='entitygroup',
            name='entities',
            field=models.ManyToManyField(to='entity.Entity', through='entity.EntityGroupMembership'),
            preserve_default=True,
        ),
    ]
