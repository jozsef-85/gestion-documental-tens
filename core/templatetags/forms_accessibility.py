from django import template
from django.utils.safestring import mark_safe


register = template.Library()


def _field_base_id(bound_field):
    return bound_field.auto_id or bound_field.html_name


@register.filter
def field_help_id(bound_field):
    if not getattr(bound_field, 'help_text', ''):
        return ''
    return f'{_field_base_id(bound_field)}-help'


@register.filter
def field_error_id(bound_field):
    return f'{_field_base_id(bound_field)}-error'


@register.filter
def field_describedby(bound_field):
    describedby = []
    if getattr(bound_field, 'help_text', ''):
        describedby.append(field_help_id(bound_field))
    if getattr(bound_field, 'errors', None):
        describedby.append(field_error_id(bound_field))
    return ' '.join(describedby)


@register.filter
def render_field_a11y(bound_field):
    attrs = {
        'aria-invalid': 'true' if bound_field.errors else 'false',
    }
    if bound_field.field.required:
        attrs['aria-required'] = 'true'

    describedby = field_describedby(bound_field)
    if describedby:
        attrs['aria-describedby'] = describedby

    return mark_safe(bound_field.as_widget(attrs=attrs))
