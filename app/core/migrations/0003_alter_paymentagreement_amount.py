# Generated by Django 5.1.5 on 2025-02-01 12:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_paymentagreement'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentagreement',
            name='amount',
            field=models.DecimalField(decimal_places=2, max_digits=15),
        ),
    ]
