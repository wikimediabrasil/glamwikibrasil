import urllib.parse
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

@register.filter
def wiki_page(url):
    page_title = urllib.parse.unquote(urllib.parse.urlparse(url).path.replace('/wiki/', ''))
    formatted_title = page_title.replace('_', ' ')
    return formatted_title