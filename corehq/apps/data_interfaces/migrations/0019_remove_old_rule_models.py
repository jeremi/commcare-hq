# -*- coding: utf-8 -*-
# Generated by Django 1.11.14 on 2018-09-11 15:24
from __future__ import unicode_literals
from __future__ import absolute_import
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0018_check_for_rule_migration'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='automaticupdateaction',
            name='rule',
        ),
        migrations.RemoveField(
            model_name='automaticupdaterulecriteria',
            name='rule',
        ),
        migrations.DeleteModel(
            name='AutomaticUpdateAction',
        ),
        migrations.DeleteModel(
            name='AutomaticUpdateRuleCriteria',
        ),
    ]
