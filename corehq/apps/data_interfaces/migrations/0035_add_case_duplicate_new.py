# Generated by Django 3.2.23 on 2023-12-18 18:49

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data_interfaces', '0034_case_name_actions'),
    ]

    operations = [
        migrations.CreateModel(
            name='CaseDuplicateNew',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('case_id', models.CharField(db_index=True, max_length=126)),
                ('hash', models.CharField(max_length=256)),
                ('action', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='data_interfaces.casededuplicationactiondefinition')),
            ],
            options={
                'db_table': 'data_interfaces_caseduplicate_new',
            },
        ),
        migrations.AddIndex(
            model_name='caseduplicatenew',
            index=models.Index(fields=['hash', 'action_id'], name='data_interf_hash_a070d8_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='caseduplicatenew',
            unique_together={('case_id', 'action')},
        ),
    ]
