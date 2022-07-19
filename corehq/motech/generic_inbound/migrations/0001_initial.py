# Generated by Django 3.2.13 on 2022-07-19 15:19

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import re


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('userreports', '0019_ucrexpression_upstream_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfigurableAPI',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(max_length=255)),
                ('key', models.CharField(max_length=32, validators=[django.core.validators.RegexValidator(re.compile('^[-a-zA-Z0-9_]+\\Z'), 'Enter a valid “slug” consisting of letters, numbers, underscores or hyphens.', 'invalid')])),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('transform_expression', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='userreports.ucrexpression')),
            ],
            options={
                'unique_together': {('domain', 'key')},
            },
        ),
    ]
