# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('entity', '0004_auto_20150915_1747'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='entitygroup',
            name='entities',
        ),
    ]
