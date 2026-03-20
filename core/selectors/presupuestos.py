from django.db.models import Count, F, OuterRef, Q, Subquery, Sum

from ..domain.presupuestos_status import (
    EN_PROCESO,
    FACTURADO,
    PAGADO,
    PENDIENTE,
    estado_resumen_label,
    q_aceptado,
    q_aceptado_efectivo,
    q_en_proceso,
    q_estado_presupuesto,
    q_estado_manual_vacio,
    q_facturado,
    q_pagado,
    q_pendiente_por_cobrar,
)
from ..models import RegistroPresupuesto


def inventario_presupuestos_queryset():
    # Una misma referencia de presupuesto puede aparecer en varias cargas historicas
    # del Excel. Para operar el dia a dia se toma solo el ultimo registro vigente.
    ultimo_registro = RegistroPresupuesto.objects.filter(
        presupuesto=OuterRef('presupuesto')
    ).order_by('-carga__fecha_carga', '-id')

    return RegistroPresupuesto.objects.select_related('carga', 'carga__creado_por', 'trabajo').annotate(
        ultimo_id=Subquery(ultimo_registro.values('id')[:1])
    ).filter(id=F('ultimo_id'))


def filtrar_por_estado(queryset, estado):
    if estado == 'por_cobrar':
        return queryset.filter(q_pendiente_por_cobrar())
    if estado in {PAGADO, FACTURADO, EN_PROCESO, PENDIENTE}:
        return queryset.filter(q_estado_presupuesto(estado))
    return queryset


def resumir_flujo(queryset):
    # Este resumen alimenta dashboard e indicadores con un lenguaje cercano al negocio,
    # no al detalle tecnico de cada campo almacenado.
    etapas = [
        (estado_resumen_label(PENDIENTE), q_estado_presupuesto(PENDIENTE)),
        (estado_resumen_label(EN_PROCESO), q_estado_presupuesto(EN_PROCESO)),
        ('Con guía de despacho', Q(guia_despacho__gt='')),
        (estado_resumen_label(FACTURADO), q_estado_presupuesto(FACTURADO) | q_estado_presupuesto(PAGADO)),
        (estado_resumen_label(PAGADO), q_estado_presupuesto(PAGADO)),
    ]
    resumen = []
    for etiqueta, condicion in etapas:
        subset = queryset.filter(condicion)
        resumen.append({
            'etiqueta': etiqueta,
            'cantidad': subset.count(),
            'total_monto': subset.filter(q_aceptado()).aggregate(total=Sum('monto'))['total'] or 0,
        })
    return resumen


def aggregate_presupuesto_metrics(queryset):
    # Estas metricas concentran la lectura ejecutiva del control: aceptados,
    # ejecucion, facturados, pagados y monto aun por cobrar.
    return queryset.aggregate(
        total_items=Count('id'),
        total_pendientes_aprobacion=Count('id', filter=q_estado_presupuesto(PENDIENTE)),
        total_aceptados=Count('id', filter=q_aceptado_efectivo()),
        total_pendientes_por_cobrar=Count('id', filter=q_pendiente_por_cobrar()),
        total_en_proceso=Count('id', filter=q_estado_presupuesto(EN_PROCESO)),
        total_facturados=Count('id', filter=q_estado_presupuesto(FACTURADO)),
        total_pagados=Count('id', filter=q_estado_presupuesto(PAGADO)),
        total_activo=Count('id', filter=~q_estado_presupuesto(PAGADO)),
        monto_por_cobrar=Sum('monto', filter=q_pendiente_por_cobrar()),
    )


def actualizar_total_carga(carga):
    # Si al borrar registros una carga queda vacia, deja de tener valor operativo
    # y se elimina para no mostrar importaciones "fantasma" en la interfaz.
    total = carga.registros.count()
    if total == 0:
        carga.delete()
        return
    carga.total_registros = total
    carga.save(update_fields=['total_registros'])
