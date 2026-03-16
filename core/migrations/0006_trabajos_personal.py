from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_trabajos_presupuesto(apps, schema_editor):
    RegistroPresupuesto = apps.get_model('core', 'RegistroPresupuesto')
    TrabajoPresupuesto = apps.get_model('core', 'TrabajoPresupuesto')

    presupuestos = sorted({
        (presupuesto or '').strip()
        for presupuesto in RegistroPresupuesto.objects.values_list('presupuesto', flat=True)
        if (presupuesto or '').strip()
    })
    if not presupuestos:
        return

    existentes = {
        trabajo.presupuesto: trabajo.id
        for trabajo in TrabajoPresupuesto.objects.filter(presupuesto__in=presupuestos)
    }
    faltantes = [
        TrabajoPresupuesto(presupuesto=presupuesto)
        for presupuesto in presupuestos
        if presupuesto not in existentes
    ]
    if faltantes:
        TrabajoPresupuesto.objects.bulk_create(faltantes, ignore_conflicts=True)
        existentes = {
            trabajo.presupuesto: trabajo.id
            for trabajo in TrabajoPresupuesto.objects.filter(presupuesto__in=presupuestos)
        }

    registros = list(RegistroPresupuesto.objects.exclude(presupuesto=''))
    for registro in registros:
        registro.trabajo_id = existentes.get((registro.presupuesto or '').strip())
    if registros:
        RegistroPresupuesto.objects.bulk_update(registros, ['trabajo'])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0005_rename_valor_registropresupuesto_monto'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrabajoPresupuesto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('presupuesto', models.CharField(max_length=200, unique=True)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['presupuesto'],
            },
        ),
        migrations.AddField(
            model_name='registropresupuesto',
            name='trabajo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='registros', to='core.trabajopresupuesto'),
        ),
        migrations.CreateModel(
            name='AsignacionTrabajo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rol', models.CharField(blank=True, max_length=120)),
                ('estado', models.CharField(choices=[('activo', 'Activo'), ('pausado', 'Pausado'), ('finalizado', 'Finalizado')], default='activo', max_length=20)),
                ('fecha_asignacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_inicio', models.DateField(blank=True, null=True)),
                ('fecha_fin', models.DateField(blank=True, null=True)),
                ('horas_estimadas', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('horas_reales', models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ('observaciones', models.TextField(blank=True)),
                ('creado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('trabajador', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='asignaciones', to='core.personaltrabajo')),
                ('trabajo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='asignaciones', to='core.trabajopresupuesto')),
            ],
            options={
                'ordering': ['-fecha_asignacion', 'trabajador__nombre'],
            },
        ),
        migrations.AddIndex(
            model_name='asignaciontrabajo',
            index=models.Index(fields=['estado'], name='asigtrab_estado_idx'),
        ),
        migrations.RunPython(backfill_trabajos_presupuesto, migrations.RunPython.noop),
    ]
