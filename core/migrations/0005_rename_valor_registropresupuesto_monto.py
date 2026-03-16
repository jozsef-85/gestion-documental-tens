from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_registropresupuesto_query_indexes'),
    ]

    operations = [
        migrations.RenameField(
            model_name='registropresupuesto',
            old_name='valor',
            new_name='monto',
        ),
    ]
