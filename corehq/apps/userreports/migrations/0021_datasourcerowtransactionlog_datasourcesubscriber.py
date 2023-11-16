# Generated by Django 3.2.23 on 2023-11-16 11:26

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('userreports', '0020_delete_ucr_comparison_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataSourceRowTransactionLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=126)),
                ('date_created', models.DateTimeField(auto_now_add=True)),
                ('action', models.CharField(choices=[('create', 'create'), ('update', 'update'), ('delete', 'delete')], max_length=32)),
                ('data_source_id', models.CharField(db_index=True, max_length=255)),
                ('row_id', models.CharField(db_index=True, max_length=255)),
                ('row_data', models.JSONField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='DataSourceSubscriber',
            fields=[
                ('domain', models.CharField(db_index=True, max_length=126)),
                ('data_source_id', models.CharField(db_index=True, max_length=255)),
                ('subscriber_uuid', models.CharField(default=uuid.uuid4, editable=False, max_length=255, primary_key=True, serialize=False)),
            ],
        ),
    ]
