# Generated by Django 2.2.27 on 2022-03-04 11:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('oauth_integrations', '0003_livegooglesheetrefreshstatus'),
    ]

    operations = [
        migrations.AlterField(
            model_name='livegooglesheetrefreshstatus',
            name='refresh_error_reason',
            field=models.CharField(choices=[(None, 'No Error'), ('token', 'Invalid Token'), ('timeout', 'Data Timeout'), ('other', 'Other...')], default=None, max_length=16, null=True),
        ),
        migrations.AlterField(
            model_name='livegooglesheetrefreshstatus',
            name='schedule',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='oauth_integrations.LiveGoogleSheetSchedule'),
        ),
    ]
