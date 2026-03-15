from django.db.models import F, OuterRef, Q, Subquery, Sum

from ..models import RegistroPresupuesto


def q_pagado():
    return Q(fecha_pago__isnull=False) | Q(fecha_pago_texto__gt='')


def q_facturado():
    return Q(fecha_facturacion__isnull=False) | Q(fecha_facturacion_texto__gt='') | Q(factura__gt='')


def q_aceptado():
    return Q(nota_pedido__gt='')


def q_en_proceso():
    return q_aceptado() & (
        Q(recepcion__gt='')
        | Q(guia_despacho__gt='')
        | Q(estado_oc__gt='')
        | Q(estado_recepcion__gt='')
    )


def q_estado_manual_vacio():
    return Q(estado_manual='') | Q(estado_manual__isnull=True)


def q_estado_presupuesto(estado):
    automatico = q_estado_manual_vacio()
    if estado == 'pagado':
        return Q(estado_manual='pagado') | (automatico & q_pagado())
    if estado == 'facturado':
        return Q(estado_manual='facturado') | (automatico & q_facturado() & ~q_pagado())
    if estado == 'en_proceso':
        return Q(estado_manual='en_proceso') | (automatico & q_aceptado() & ~q_facturado() & ~q_pagado())
    if estado == 'pendiente':
        return Q(estado_manual='pendiente') | (automatico & ~q_aceptado() & ~q_facturado() & ~q_pagado())
    return Q()


def inventario_presupuestos_queryset():
    ultimo_registro = RegistroPresupuesto.objects.filter(
        presupuesto=OuterRef('presupuesto')
    ).order_by('-carga__fecha_carga', '-id')

    return RegistroPresupuesto.objects.select_related('carga', 'carga__creado_por').annotate(
        ultimo_id=Subquery(ultimo_registro.values('id')[:1])
    ).filter(id=F('ultimo_id'))


def filtrar_por_estado(queryset, estado):
    if estado in {'pagado', 'facturado', 'en_proceso', 'pendiente'}:
        return queryset.filter(q_estado_presupuesto(estado))
    return queryset


def resumir_flujo(queryset):
    etapas = [
        ('Pendientes de aprobacion', q_estado_presupuesto('pendiente')),
        ('Aceptados / En curso', q_estado_presupuesto('en_proceso')),
        ('Con guia de despacho', Q(guia_despacho__gt='')),
        ('Realizados', q_estado_presupuesto('facturado') | q_estado_presupuesto('pagado')),
        ('Pagados', q_estado_presupuesto('pagado')),
    ]
    resumen = []
    for etiqueta, condicion in etapas:
        subset = queryset.filter(condicion)
        resumen.append({
            'etiqueta': etiqueta,
            'cantidad': subset.count(),
            'total_valor': subset.filter(q_aceptado()).aggregate(total=Sum('valor'))['total'] or 0,
        })
    return resumen


def actualizar_total_carga(carga):
    total = carga.registros.count()
    if total == 0:
        carga.delete()
        return
    carga.total_registros = total
    carga.save(update_fields=['total_registros'])
