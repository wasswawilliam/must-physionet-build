# Generated by Django 2.1.4 on 2018-12-31 21:23

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='credentialapplication',
            name='responder',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='responded_applications', to=settings.AUTH_USER_MODEL),
        ),
    ]
