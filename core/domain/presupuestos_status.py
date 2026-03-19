from django.db.models import Q

PENDIENTE = 'pendiente'
EN_PROCESO = 'en_proceso'
FACTURADO = 'facturado'
PAGADO = 'pagado'

ESTADOS_ORDENADOS = (
    PENDIENTE,
    EN_PROCESO,
    FACTURADO,
    PAGADO,
)

ESTADOS_LABELS = {
    PENDIENTE: 'Pendiente de aprobación',
    EN_PROCESO: 'Aceptado / En curso',
    FACTURADO: 'Realizado',
    PAGADO: 'Pagado',
}

ESTADOS_RESUMEN_LABELS = {
    PENDIENTE: 'Pendientes de aprobación',
    EN_PROCESO: 'Aceptados / En curso',
    FACTURADO: 'Realizados',
    PAGADO: 'Pagados',
}


def estado_choices():
    return [(codigo, ESTADOS_LABELS[codigo]) for codigo in ESTADOS_ORDENADOS]


def estado_label(codigo):
    return ESTADOS_LABELS.get(codigo, ESTADOS_LABELS[PENDIENTE])


def estado_resumen_label(codigo):
    return ESTADOS_RESUMEN_LABELS.get(codigo, ESTADOS_RESUMEN_LABELS[PENDIENTE])


def estado_codigo_desde_registro(registro):
    if registro.estado_manual:
        return registro.estado_manual
    if registro.fecha_pago or registro.fecha_pago_texto:
        return PAGADO
    if registro.factura or registro.fecha_facturacion or registro.fecha_facturacion_texto:
        return FACTURADO
    if registro.nota_pedido:
        return EN_PROCESO
    return PENDIENTE


def q_pagado():
    return Q(fecha_pago__isnull=False) | Q(fecha_pago_texto__gt='')


def q_facturado():
    return Q(fecha_facturacion__isnull=False) | Q(fecha_facturacion_texto__gt='') | Q(factura__gt='')


def q_aceptado():
    return Q(nota_pedido__gt='')


def q_en_proceso():
    return q_aceptado() & ~q_facturado() & ~q_pagado()


def q_estado_manual_vacio():
    return Q(estado_manual='') | Q(estado_manual__isnull=True)


def q_estado_presupuesto(estado):
    automatico = q_estado_manual_vacio()
    if estado == PAGADO:
        return Q(estado_manual=PAGADO) | (automatico & q_pagado())
    if estado == FACTURADO:
        return Q(estado_manual=FACTURADO) | (automatico & q_facturado() & ~q_pagado())
    if estado == EN_PROCESO:
        return Q(estado_manual=EN_PROCESO) | (automatico & q_aceptado() & ~q_facturado() & ~q_pagado())
    if estado == PENDIENTE:
        return Q(estado_manual=PENDIENTE) | (automatico & ~q_aceptado() & ~q_facturado() & ~q_pagado())
    return Q()


def q_aceptado_efectivo():
    return q_estado_presupuesto(EN_PROCESO) | q_estado_presupuesto(FACTURADO) | q_estado_presupuesto(PAGADO)


def q_pendiente_por_cobrar():
    return q_estado_presupuesto(EN_PROCESO) | q_estado_presupuesto(FACTURADO)
