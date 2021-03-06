# Generated by Django 2.0.2 on 2018-09-28 02:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inquiry', '0004_auto_20180917_1611'),
    ]

    operations = [
        migrations.AlterField(
            model_name='inquiry',
            name='rent_type',
            field=models.CharField(choices=[('no', 'No'), ('under_14', 'Yes, 14 days or fewer per year'), ('over_14', 'Yes, more than 14 days per year')], max_length=8),
        ),
        migrations.AlterField(
            model_name='inquiry',
            name='ten_year_duration_prediction',
            field=models.CharField(choices=[('over_10', 'Yes, more than 10 years'), ('10_or_less', 'No, 10 years or fewer'), ('dont_know', "Don't know")], default='10_or_less', max_length=10),
        ),
    ]
