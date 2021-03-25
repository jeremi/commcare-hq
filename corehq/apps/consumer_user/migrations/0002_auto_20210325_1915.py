# Generated by Django 2.2.16 on 2021-03-25 19:15

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL),
        ('consumer_user', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CaseRelationshipOauthToken',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'access_token',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL
                    )
                ),
                (
                    'consumer_user_case_relationship',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='consumer_user.ConsumerUserCaseRelationship'
                    )
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name='caserelationshipoauthtoken',
            constraint=models.UniqueConstraint(
                fields=('consumer_user_case_relationship', 'access_token'),
                name='unique-relationship-access-token'
            ),
        ),
    ]
