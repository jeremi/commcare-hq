# Generated by Django 3.2.19 on 2023-06-05 13:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_dictionary', '0013_auto_20230529_1614'),
    ]

    operations = [
        migrations.AddField(
            model_name='casetype',
            name='is_deprecated',
            field=models.BooleanField(default=False),
        ),
    ]
