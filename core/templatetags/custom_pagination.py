from django import template
from django.utils.http import urlencode

register = template.Library()

@register.inclusion_tag('core/custom_pagination.html', takes_context=True)
def custom_pagination(context):
    request = context.get('request')
    page_obj = context.get('page_obj')
    paginator = page_obj.paginator
    result_count = paginator.count
    opts = context.get('opts')
    pagination_required = paginator.num_pages > 1
    page_range = paginator.get_elided_page_range(number=page_obj.number, on_each_side=1, on_ends=0)
    #print(f'{page_obj.start_index()}')
    #print(f'{page_obj.end_index()}')
    # build query_string from POST or GET
    if request.method == 'POST' and request.POST:
        get_params = request.POST.copy()
        # remove csrf + empty values
        if 'csrfmiddlewaretoken' in get_params:
            get_params.pop('csrfmiddlewaretoken')
        for k in list(get_params.keys()):
            if get_params[k] == '':
                get_params.pop(k)
    else:
        get_params = request.GET.copy()
        if 'page' in get_params:
            get_params.pop('page')
    # use .lists() and urlencode with doseq=True
    query_string = ''
    if get_params:
        query_string = '&' + urlencode(list(get_params.lists()), doseq=True)

    return {
        'cl': page_obj,
        'result_count': result_count,
        'opts': opts,
        'pagination_required': pagination_required,
        'page_range': page_range,
        'query_string': query_string,
    }
