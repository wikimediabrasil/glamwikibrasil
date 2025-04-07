from math import floor
from datetime import datetime
from django import template

register = template.Library()

@register.filter
def divide(a, b):
    try:
        return floor(a/b)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0

@register.filter
def timestamp2date(timestamp):
    return datetime.strptime(timestamp, "%Y%m%d00")