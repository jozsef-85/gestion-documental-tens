from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.template.loader import render_to_string

from ..selectors.presupuestos import inventario_presupuestos_queryset, q_estado_presupuesto


def obtener_facturas_pendientes_queryset():
    return (
        inventario_presupuestos_queryset()
        .select_related('cliente')
        .filter(q_estado_presupuesto('facturado'))
        .exclude(Q(fecha_pago__isnull=False) | Q(fecha_pago_texto__gt=''))
        .order_by('cliente__nombre', 'fecha_facturacion', 'presupuesto')
    )


def _dias_desde_facturacion(registro):
    if registro.fecha_facturacion:
        return (date.today() - registro.fecha_facturacion).days
    return None


def construir_resumen_cobranzas(registros):
    items = []
    total_monto = Decimal('0')
    total_con_email = 0
    total_sin_email = 0

    for registro in registros:
        monto = registro.monto or Decimal('0')
        total_monto += monto
        email_cliente = (getattr(registro.cliente, 'email', '') or '').strip()
        if email_cliente:
            total_con_email += 1
        else:
            total_sin_email += 1
        items.append({
            'registro': registro,
            'cliente_nombre': getattr(registro.cliente, 'nombre', '') or 'Sin cliente',
            'cliente_email': email_cliente,
            'dias_pendiente': _dias_desde_facturacion(registro),
            'monto': monto,
        })

    return {
        'items': items,
        'total_registros': len(items),
        'total_monto': total_monto,
        'total_con_email': total_con_email,
        'total_sin_email': total_sin_email,
        'app_url': settings.COBRANZA_APP_URL,
    }


def agrupar_registros_por_cliente(registros):
    agrupados = defaultdict(list)
    for registro in registros:
        email = (getattr(registro.cliente, 'email', '') or '').strip().lower()
        if not email:
            continue
        agrupados[email].append(registro)
    return agrupados


def enviar_resumen_operador(registros, destinatarios=None, dry_run=False):
    destinatarios = list(destinatarios or settings.COBRANZA_OPERATOR_EMAILS)
    if not destinatarios:
        return {'enviado': False, 'motivo': 'sin_destinatarios', 'total_registros': 0}

    registros = list(registros)
    contexto = construir_resumen_cobranzas(registros)
    contexto['destinatarios'] = destinatarios
    subject = f"[Cobranza] {contexto['total_registros']} factura(s) pendiente(s) de pago"
    body = render_to_string('emails/cobranza_operador.txt', contexto)

    if dry_run:
        return {
            'enviado': False,
            'motivo': 'dry_run',
            'total_registros': contexto['total_registros'],
            'destinatarios': destinatarios,
            'subject': subject,
            'body': body,
        }

    mensaje = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=destinatarios,
        reply_to=settings.COBRANZA_REPLY_TO or None,
    )
    mensaje.send(fail_silently=False)
    return {
        'enviado': True,
        'motivo': 'ok',
        'total_registros': contexto['total_registros'],
        'destinatarios': destinatarios,
    }


def enviar_recordatorios_clientes(registros, dry_run=False):
    agrupados = agrupar_registros_por_cliente(registros)
    enviados = []

    for email_cliente, items in agrupados.items():
        cliente = items[0].cliente if items else None
        contexto = {
            'cliente': cliente,
            'registros': [
                {
                    'registro': item,
                    'dias_pendiente': _dias_desde_facturacion(item),
                }
                for item in items
            ],
            'app_url': settings.COBRANZA_APP_URL,
        }
        subject = f"[Cobranza] Recordatorio de factura(s) pendiente(s) - {getattr(cliente, 'nombre', 'Cliente')}"
        body = render_to_string('emails/cobranza_cliente.txt', contexto)

        if not dry_run:
            mensaje = EmailMultiAlternatives(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email_cliente],
                reply_to=settings.COBRANZA_REPLY_TO or None,
            )
            mensaje.send(fail_silently=False)

        enviados.append({
            'cliente': getattr(cliente, 'nombre', 'Cliente'),
            'email': email_cliente,
            'cantidad_registros': len(items),
            'dry_run': dry_run,
        })

    return enviados
