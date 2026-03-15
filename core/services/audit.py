from .helpers import obtener_ip_cliente
from ..models import Auditoria


def registrar_auditoria(request, accion, entidad, entidad_id=None, detalle=''):
    Auditoria.objects.create(
        usuario=request.user,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        detalle=detalle,
        ip=obtener_ip_cliente(request),
    )
