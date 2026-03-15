import logging

from django.shortcuts import render

from .services.helpers import obtener_ip_cliente


security_logger = logging.getLogger('security')


def permission_denied_view(request, exception=None):
    security_logger.warning(
        'Acceso denegado: path=%s user=%s ip=%s reason=%s',
        request.path,
        getattr(request.user, 'username', 'anonimo'),
        obtener_ip_cliente(request),
        exception or 'permission_denied',
    )
    return render(request, '403.html', status=403)


def csrf_failure(request, reason=''):
    security_logger.warning(
        'Fallo CSRF: path=%s user=%s ip=%s reason=%s',
        request.path,
        getattr(request.user, 'username', 'anonimo'),
        obtener_ip_cliente(request),
        reason,
    )
    return render(request, '403.html', {'csrf_failure': True}, status=403)
