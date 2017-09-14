# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-09-14 17:58
from __future__ import unicode_literals

from django.db import migrations

from corehq.blobs import get_blob_db
from corehq.sql_db.operations import HqRunPython

FIXTURE_BUCKET = 'domain-fixtures'


def rm_blobdb_domain_fixtures(apps, schema_editor):
    get_blob_db().delete(bucket=FIXTURE_BUCKET)


def noop_reverse_migration(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('fixtures', '0002_rm_blobdb_domain_fixtures'),
    ]

    operations = [
        HqRunPython(rm_blobdb_domain_fixtures, noop_reverse_migration),
    ]
