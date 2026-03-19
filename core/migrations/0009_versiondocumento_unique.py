from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_personaltrabajo_afiliacion_mutualidad_and_more'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='versiondocumento',
            constraint=models.UniqueConstraint(
                fields=('documento', 'numero_version'),
                name='versiondoc_documento_numero_unique',
            ),
        ),
    ]
