# Generated by Django 2.1.7 on 2019-04-12 17:35

from django.db import migrations, models
import project.validators


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0012_auto_20190405_1744'),
    ]

    operations = [
        migrations.AlterField(
            model_name='publishedproject',
            name='slug',
            field=models.SlugField(max_length=20, validators=[project.validators.validate_slug]),
        ),
    ]
