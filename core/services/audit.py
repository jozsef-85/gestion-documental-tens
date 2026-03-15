import logging

from django.core.cache import cache

from .helpers import obtener_ip_cliente
from ..models import Auditoria


security_logger = logging.getLogger('security')
ALERT_CACHE_KEY = 'core.audit.failure.alerted'
ALERT_CACHE_TIMEOUT = 300


def registrar_auditoria(request, accion, entidad, entidad_id=None, detalle=''):
    try:
        Auditoria.objects.create(
            usuario=request.user,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            detalle=detalle,
            ip=obtener_ip_cliente(request),
        )
    except Exception as exc:
        security_logger.exception(
            'Fallo al registrar auditoría: accion=%s entidad=%s entidad_id=%s user=%s error=%s',
            accion,
            entidad,
            entidad_id,
            getattr(request.user, 'username', 'anonimo'),
            exc,
        )
        if not cache.get(ALERT_CACHE_KEY):
            security_logger.critical(
                'La auditoría está fallando y se están perdiendo eventos. Revisar base de datos o almacenamiento de inmediato.'
            )
            cache.set(ALERT_CACHE_KEY, True, ALERT_CACHE_TIMEOUT)
