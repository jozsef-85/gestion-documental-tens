from functools import wraps
import logging

from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .helpers import obtener_ip_cliente


security_logger = logging.getLogger('security')


def any_permission_required(*perms):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_superuser or any(request.user.has_perm(perm) for perm in perms):
                return view_func(request, *args, **kwargs)
            security_logger.warning(
                'Permiso insuficiente: path=%s user=%s ip=%s required_any=%s',
                request.path,
                getattr(request.user, 'username', 'anonimo'),
                obtener_ip_cliente(request),
                ','.join(perms),
            )
            raise PermissionDenied

        return _wrapped_view

    return decorator


def model_access_required(app_label, model_name):
    model_name = model_name.lower()
    return any_permission_required(f'{app_label}.view_{model_name}')


def usuario_confidencialidad_alta(user):
    # "Confidencialidad alta" se reserva a perfiles con capacidad real de
    # administracion documental, no solo a usuarios autenticados.
    if not getattr(user, 'is_authenticated', False):
        return False
    return (
        user.is_superuser
        or user.has_perm('core.change_documento')
        or user.groups.filter(name='Administradores').exists()
    )


def filtrar_documentos_por_confidencialidad(queryset, user):
    # Un usuario comun puede ver documentos de baja/media y los que el mismo creo.
    # Con eso se protege informacion sensible sin bloquear el trabajo cotidiano.
    if usuario_confidencialidad_alta(user):
        return queryset
    return queryset.filter(
        Q(nivel_confidencialidad__in=['baja', 'media'])
        | Q(creado_por=user)
    )


def validar_acceso_documento(request, documento):
    # La descarga pasa por una validacion explicita para no exponer archivos de
    # alta confidencialidad solo por conocer una URL o un identificador.
    if documento.nivel_confidencialidad != 'alta':
        return
    if usuario_confidencialidad_alta(request.user):
        return
    if documento.creado_por_id == getattr(request.user, 'id', None):
        return
    security_logger.warning(
        'Acceso restringido por confidencialidad: path=%s user=%s ip=%s documento_id=%s nivel=%s',
        request.path,
        getattr(request.user, 'username', 'anonimo'),
        obtener_ip_cliente(request),
        documento.id,
        documento.nivel_confidencialidad,
    )
    raise PermissionDenied
