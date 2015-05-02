# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('entity', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='entitykind',
            name='is_active',
            field=models.BooleanField(default=True),
            preserve_default=True,
        ),
    ]
