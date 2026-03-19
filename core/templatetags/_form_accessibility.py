from django.utils.safestring import mark_safe


def field_base_id(bound_field):
    return bound_field.auto_id or bound_field.html_name


def field_help_id(bound_field):
    if not getattr(bound_field, 'help_text', ''):
        return ''
    return f'{field_base_id(bound_field)}-help'


def field_error_id(bound_field):
    return f'{field_base_id(bound_field)}-error'


def field_describedby(bound_field):
    describedby = (
        field_help_id(bound_field),
        field_error_id(bound_field) if getattr(bound_field, 'errors', None) else '',
    )
    return ' '.join(filter(None, describedby))


def render_field_a11y(bound_field):
    widget_attrs = {
        'aria-invalid': 'true' if bound_field.errors else 'false',
    }
    if bound_field.field.required:
        widget_attrs['aria-required'] = 'true'

    describedby = field_describedby(bound_field)
    if describedby:
        widget_attrs['aria-describedby'] = describedby

    return mark_safe(bound_field.as_widget(attrs=widget_attrs))
