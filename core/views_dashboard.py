from django.contrib.auth.decorators import login_required
from django.db.models import Case, Sum, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils.timezone import localtime

from .models import CargaPresupuesto, RegistroPresupuesto
from .selectors.presupuestos import (
    inventario_presupuestos_queryset,
    q_aceptado,
    q_estado_presupuesto,
    q_pagado,
)
from .services.access import model_access_required
from .services.indicators import obtener_indicadores


@login_required
@model_access_required('core', 'registropresupuesto')
def dashboard(request):
    indicadores = obtener_indicadores()
    ahora = localtime()
    inventario_actual = inventario_presupuestos_queryset().prefetch_related('documentos')
    total_inventario = inventario_actual.count()
    total_con_nota_pedido = inventario_actual.filter(q_aceptado()).count()
    total_pendientes_por_cobrar = inventario_actual.filter(q_aceptado()).exclude(q_pagado()).count()
    total_en_ejecucion = inventario_actual.filter(q_estado_presupuesto('en_proceso')).count()
    total_realizados = inventario_actual.filter(q_estado_presupuesto('facturado')).count()
    total_pagados = inventario_actual.filter(q_estado_presupuesto('pagado')).count()
    total_monto_por_cobrar = inventario_actual.filter(q_aceptado()).exclude(q_pagado()).aggregate(total=Sum('valor'))['total'] or 0
    dashboard_registros = list(
        inventario_actual.select_related('carga', 'actualizado_por').annotate(
            fecha_gestion=Coalesce('fecha_actualizacion', 'carga__fecha_carga'),
            orden_nota=Case(
                When(q_aceptado(), then=Value(1)),
                default=Value(0),
            ),
        ).order_by('-orden_nota', '-fecha_gestion', 'presupuesto')[:12]
    )
    ultimos_presupuestos = list(
        inventario_actual.select_related('carga').order_by('-carga__fecha_carga', 'presupuesto')[:6]
    )
    alertas = [
        {
            'cantidad': total_pendientes_por_cobrar,
            'titulo': 'Pendientes por cobrar',
            'detalle': 'Trabajos aceptados con nota de pedido que aún no pasan a estado pagado.',
        },
        {
            'titulo': 'Trabajos pagados',
            'cantidad': total_pagados,
            'detalle': 'Trabajos cerrados con pago registrado.',
        },
    ]

    return render(request, 'dashboard.html', {
        'total_inventario_presupuestos': total_inventario,
        'total_con_nota_pedido': total_con_nota_pedido,
        'total_pendientes_por_cobrar': total_pendientes_por_cobrar,
        'total_en_ejecucion': total_en_ejecucion,
        'total_realizados_dashboard': total_realizados,
        'total_pagados_dashboard': total_pagados,
        'total_monto_por_cobrar': total_monto_por_cobrar,
        'total_activo': inventario_actual.exclude(q_estado_presupuesto('pagado')).count(),
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
