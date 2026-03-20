from django import template


register = template.Library()


EDITOR_PERMS = (
    'core.add_asignaciontrabajo',
    'core.add_cargapresupuesto',
    'core.add_cliente',
    'core.add_documento',
    'core.add_personaltrabajo',
    'core.add_registropresupuesto',
    'core.change_cliente',
    'core.change_documento',
    'core.change_personaltrabajo',
    'core.change_registropresupuesto',
)

LECTOR_PERMS = (
    'core.view_cliente',
    'core.view_documento',
    'core.view_personaltrabajo',
    'core.view_registropresupuesto',
)


@register.filter
def role_label(user):
    if not getattr(user, 'is_authenticated', False):
        return ''

    if user.is_superuser or user.groups.filter(name='Administradores').exists():
        return 'Administrador'
    if user.groups.filter(name='Editores').exists():
        return 'Editor'
    if user.groups.filter(name='Lectores').exists():
        return 'Lector'
    if any(user.has_perm(perm) for perm in EDITOR_PERMS):
        return 'Editor'
    if any(user.has_perm(perm) for perm in LECTOR_PERMS):
        return 'Lector'
    return 'Usuario'
