from django import template

register = template.Library()

@register.inclusion_tag('ocmscore/pagination.html', takes_context=True)
def pagination(context, cl):
    return {'cl': cl, 'request': context['request']}

@register.simple_tag
def header_class(header, forloop):
    """Returns the CSS class for the header."""
    classes = ['sortable'] if header['sortable'] else []
    if header['sorted']:
        classes.append('sorted ascending' if header['ascending'] else 'sorted descending')
    return ' '.join(classes)

@register.simple_tag
def calculate_colspan(can_change, can_delete, can_detailview, change_url, delete_url, detail_url):
    colspan = 0
    if can_change and change_url:
        colspan += 1
    if can_delete and delete_url:
        colspan += 1
    if can_detailview and detail_url:
        colspan += 1
    return colspan
