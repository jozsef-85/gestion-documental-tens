from django import template

from ._form_accessibility import (
    field_describedby as _field_describedby,
    field_error_id as _field_error_id,
    field_help_id as _field_help_id,
    render_field_a11y as _render_field_a11y,
)

register = template.Library()

@register.filter
def field_help_id(bound_field):
    return _field_help_id(bound_field)


@register.filter
def field_error_id(bound_field):
    return _field_error_id(bound_field)


@register.filter
def field_describedby(bound_field):
    return _field_describedby(bound_field)


@register.filter
def render_field_a11y(bound_field):
    return _render_field_a11y(bound_field)
