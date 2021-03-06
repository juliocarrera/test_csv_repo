# Generated by Django 2.0.2 on 2018-07-19 17:38

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inquiry', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='inquiry',
            name='use_case_emergency',
            field=models.BooleanField(default=False, verbose_name='Needs to pay for an emergency expense'),
        ),
        migrations.AddField(
            model_name='inquiry',
            name='use_case_retirement',
            field=models.BooleanField(default=False, verbose_name='Wants to pay for retirement'),
        ),
        migrations.AlterField(
            model_name='inquiry',
            name='property_type',
            field=models.CharField(choices=[('sf', 'Single-Family Home'), ('mf', 'Multi-Family Home'), ('co', 'Condo, Townhouse or Apartment'), ('va', 'Vacation or Rental Property')], max_length=2),
        ),
        migrations.AlterField(
            model_name='inquiry',
            name='sqft',
            field=models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1)]),
        ),
        migrations.AlterField(
            model_name='inquiry',
            name='use_case_business',
            field=models.BooleanField(default=False, verbose_name='Wants to fund a business'),
        ),
        migrations.AlterField(
            model_name='inquiry',
            name='use_case_buy_home',
            field=models.BooleanField(default=False, verbose_name='Wants to buy another home'),
        ),
        migrations.AlterField(
            model_name='inquiry',
            name='use_case_debts',
            field=models.BooleanField(default=False, verbose_name='Needs help with debts'),
        ),
        migrations.AlterField(
            model_name='inquiry',
            name='use_case_diversify',
            field=models.BooleanField(default=False, verbose_name='Wants to diversify'),
        ),
        migrations.AlterField(
            model_name='inquiry',
            name='use_case_education',
            field=models.BooleanField(default=False, verbose_name='Needs help paying for education'),
        ),
        migrations.AlterField(
            model_name='inquiry',
            name='use_case_renovate',
            field=models.BooleanField(default=False, verbose_name='Wants to renovate'),
        ),
    ]
