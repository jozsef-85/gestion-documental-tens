from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


@register.filter
def clp(valor):
    if valor in (None, ''):
        return 'Sin valor'
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return valor
    entero = int(numero)
    return '$ ' + f'{entero:,}'.replace(',', '.')
