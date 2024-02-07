# Generated by Django 2.1.7 on 2019-05-14 16:56

from django.db import migrations, models
import user.validators


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0008_auto_20190510_1220'),
    ]

    operations = [
        migrations.AlterField(
            model_name='credentialapplication',
            name='state_province',
            field=models.CharField(blank=True, default='', max_length=100, validators=[user.validators.validate_alphaplusplus]),
        ),
    ]
