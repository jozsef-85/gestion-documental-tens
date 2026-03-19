from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_asignaciontrabajo_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='personaltrabajo',
            name='run',
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
    ]
