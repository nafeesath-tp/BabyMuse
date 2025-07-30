# shop/templatetags/cart_extras.py
from django import template

register = template.Library()


@register.filter
def mul(value, arg):
    try:
        return float(value) * int(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def equals(val1, val2):
    """Returns True if val1 == val2 (as string), else False."""
    return str(val1) == str(val2)
