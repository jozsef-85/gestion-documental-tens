from django.contrib.auth.models import Group, Permission


ROLE_PERMISSIONS = {
    'Administradores': None,
    'Editores': [
        'add_asignaciontrabajo',
        'change_registropresupuesto',
        'view_cliente',
        'view_documento',
        'view_personaltrabajo',
        'view_registropresupuesto',
    ],
    'Lectores': [
        'view_cliente',
        'view_documento',
        'view_personaltrabajo',
        'view_registropresupuesto',
    ],
}


def sync_role_groups_permissions():
    grupos = {}
    for nombre_grupo, codenames in ROLE_PERMISSIONS.items():
        grupo, _ = Group.objects.get_or_create(name=nombre_grupo)
        if codenames is None:
            permisos = Permission.objects.filter(content_type__app_label='core')
        else:
            permisos = Permission.objects.filter(content_type__app_label='core', codename__in=codenames)
        grupo.permissions.set(permisos)
        grupos[nombre_grupo] = grupo
    return grupos
