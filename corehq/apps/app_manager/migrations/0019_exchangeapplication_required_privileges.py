# Generated by Django 2.2.24 on 2021-09-14 17:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_manager', '0018_migrate_case_search_labels'),
    ]

    operations = [
        migrations.AddField(
            model_name='exchangeapplication',
            name='required_privileges',
            field=models.TextField(null=True, help_text="Space-separated list of privilege strings from "
                                                        "corehq.privileges"),
        ),
    ]
