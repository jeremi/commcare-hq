# Generated by Django 3.2.13 on 2022-07-03 17:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domain', '0013_accountconfirmationsettings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accountconfirmationsettings',
            name='project_name',
            field=models.CharField(default='Commcare HQ', max_length=30),
        ),
    ]
