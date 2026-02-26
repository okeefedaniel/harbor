"""Template tags for sortable table column headers."""
from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def sortable_th(context, field, label, css_class=''):
    """Render a sortable ``<th>`` element.

    Usage::

        {% load sortable_tags %}
        {% sortable_th 'title' 'Title' %}
        {% sortable_th 'amount' 'Amount' 'text-end' %}

    Requires ``current_sort``, ``current_dir``, and ``filter_params``
    in the template context (provided by ``SortableListMixin``).
    """
    current_sort = context.get('current_sort', '')
    current_dir = context.get('current_dir', 'asc')
    filter_params = context.get('filter_params', '')

    fp = f'&amp;{filter_params}' if filter_params else ''

    if current_sort == field and current_dir == 'asc':
        href = f'?sort={field}&amp;dir=desc{fp}'
        icon = '<i class="bi bi-sort-up-alt"></i>'
    elif current_sort == field and current_dir == 'desc':
        href = f'?sort={field}&amp;dir=asc{fp}'
        icon = '<i class="bi bi-sort-down"></i>'
    else:
        href = f'?sort={field}&amp;dir=asc{fp}'
        icon = '<i class="bi bi-chevron-expand"></i>'

    cls = f' {css_class}' if css_class else ''
    return format_html(
        '<th class="sortable-header{cls}">'
        '<a href="{href}">{label} {icon}</a>'
        '</th>',
        cls=mark_safe(cls),
        href=mark_safe(href),
        label=label,
        icon=mark_safe(icon),
    )
