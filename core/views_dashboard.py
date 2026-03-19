from django.contrib.auth.decorators import login_required
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.urls import reverse
from django.utils.timezone import localtime

from .models import CargaPresupuesto, RegistroPresupuesto
from .selectors.presupuestos import (
    aggregate_presupuesto_metrics,
    inventario_presupuestos_queryset,
    q_estado_presupuesto,
)
from .services.access import model_access_required
from .services.indicators import obtener_indicadores


@login_required
@model_access_required('core', 'registropresupuesto')
def dashboard(request):
    indicadores = obtener_indicadores()
    ahora = localtime()
    inventario_actual = inventario_presupuestos_queryset().prefetch_related('documentos')
    resumen = aggregate_presupuesto_metrics(inventario_actual)
    dashboard_registros = list(
        inventario_actual.filter(q_estado_presupuesto('en_proceso')).select_related('carga', 'actualizado_por').annotate(
            fecha_gestion=Coalesce('fecha_actualizacion', 'carga__fecha_carga'),
        ).order_by('-fecha_gestion', 'presupuesto')[:12]
    )
    ultimos_presupuestos = list(
        inventario_actual.select_related('carga').order_by('-carga__fecha_carga', 'presupuesto')[:6]
    )
    alertas = [
        {
            'cantidad': resumen['total_pendientes_por_cobrar'],
            'titulo': 'Pendientes por cobrar',
            'detalle': 'Trabajos aceptados o realizados que aún no pasan a estado pagado.',
            'url': f"{reverse('listar_presupuestos')}?estado=por_cobrar",
            'cta': 'Ver seguimiento',
        },
        {
            'titulo': 'Trabajos pagados',
            'cantidad': resumen['total_pagados'],
            'detalle': 'Trabajos cerrados con pago registrado.',
            'url': f"{reverse('listar_presupuestos')}?estado=pagado",
            'cta': 'Ver pagados',
        },
    ]

    return render(request, 'dashboard.html', {
        'total_inventario_presupuestos': resumen['total_items'],
        'total_con_nota_pedido': resumen['total_aceptados'],
        'total_pendientes_por_cobrar': resumen['total_pendientes_por_cobrar'],
        'total_en_ejecucion': resumen['total_en_proceso'],
        'total_realizados_dashboard': resumen['total_facturados'],
        'total_pagados_dashboard': resumen['total_pagados'],
        'total_monto_por_cobrar': resumen['monto_por_cobrar'] or 0,
        'total_activo': resumen['total_activo'],
        'total_cargas_presupuesto': CargaPresupuesto.objects.count(),
        'total_registros_presupuesto': RegistroPresupuesto.objects.count(),
        'ultima_carga_presupuesto': CargaPresupuesto.objects.first(),
        'dashboard_registros': dashboard_registros,
        'ultimos_presupuestos': ultimos_presupuestos,
        'alertas': alertas,
        'fecha_actual': ahora,
        'uf': indicadores['uf'],
        'dolar': indicadores['dolar'],
        'utm': indicadores['utm'],
        'es_admin': request.user.is_superuser or request.user.groups.filter(name='Administradores').exists(),
        'es_editor': request.user.groups.filter(name='Editores').exists(),
        'es_lector': request.user.groups.filter(name='Lectores').exists(),
    })
