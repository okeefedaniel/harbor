from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """Look up a key in a dictionary. Returns None if not found.

    Usage: {{ my_dict|dict_get:some_key }}
    """
    if isinstance(d, dict):
        return d.get(str(key))
    return None
