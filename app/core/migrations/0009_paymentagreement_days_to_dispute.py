# Generated by Django 5.1.5 on 2025-02-11 14:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_alter_paymentagreement_currency'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentagreement',
            name='days_to_dispute',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
