# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('entity', '0003_auto_20150813_2234'),
    ]

    operations = [
        migrations.AlterField(
            model_name='entitygroupmembership',
            name='entity',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='entity.Entity', null=True),
        ),
    ]
