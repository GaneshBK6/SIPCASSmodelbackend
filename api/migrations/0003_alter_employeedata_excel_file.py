# Generated by Django 4.2.11 on 2025-05-23 11:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_alter_employeedata_excel_file'),
    ]

    operations = [
        migrations.AlterField(
            model_name='employeedata',
            name='excel_file',
            field=models.FileField(upload_to='excel_uploads/'),
        ),
    ]
