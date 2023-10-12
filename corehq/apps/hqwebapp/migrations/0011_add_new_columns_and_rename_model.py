# Generated by Django 3.2.20 on 2023-10-10 09:50

import corehq.sql_db.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hqwebapp', '0010_maintenancealert_scheduling'),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenancealert',
            name='created_by_domain',
            field=corehq.sql_db.fields.CharIdField(db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='maintenancealert',
            name='created_by_user',
            field=corehq.sql_db.fields.CharIdField(max_length=128, null=True),
        ),
        migrations.AlterModelTable(
            name='maintenancealert',
            table='hqwebapp_maintenancealert',
        ),
        migrations.RenameModel(
            old_name='MaintenanceAlert',
            new_name='CommCareHQAlert',
        ),
    ]
