from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_versiondocumento_unique'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='asignaciontrabajo',
            constraint=models.UniqueConstraint(
                fields=('trabajo', 'trabajador'),
                name='asigtrab_trabajo_trabajador_unique',
            ),
        ),
    ]
