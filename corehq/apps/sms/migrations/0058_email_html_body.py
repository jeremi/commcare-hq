# Generated by Django 3.2.20 on 2023-11-06 14:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0057_fcm_content_type_messaging_events'),
    ]

    operations = [
        migrations.AddField(
            model_name='email',
            name='html_body',
            field=models.TextField(null=True),
        ),
    ]
