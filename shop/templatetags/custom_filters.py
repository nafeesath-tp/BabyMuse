from django import template
import os

register = template.Library()

@register.filter
def equals_id(value, arg):
    return value == arg

@register.filter
def basename(path):
    return os.path.basename(path)