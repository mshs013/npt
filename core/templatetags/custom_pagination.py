from django import template

register = template.Library()

@register.inclusion_tag('core/custom_pagination.html', takes_context=True)
def custom_pagination(context):
    page_obj = context.get('page_obj')
    paginator = page_obj.paginator
    result_count = paginator.count
    opts = context.get('opts')
    pagination_required = paginator.num_pages > 1
    page_range = paginator.get_elided_page_range(number=page_obj.number, on_each_side=1, on_ends=0)
    #print(f'{page_obj.start_index()}')
    #print(f'{page_obj.end_index()}')
    return {
        'cl': page_obj,
        'result_count': result_count,
        'opts': opts,
        'pagination_required': pagination_required,
        'page_range': page_range,
    }
