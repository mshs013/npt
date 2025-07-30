from core.utils.views import dynamic_view, dynamic_form_view, dynamic_delete_view

# Create your views here.
def reason(request):
    list_display = ('name', 'min_time', 'remote_num', 'created_by', 'created_at', 'updated_by', 'updated_at',)
    default_sort = ['remote_num']  # Default sorting by name ascending and created_at descending
    list_filter = ('name', 'min_time', 'remote_num')  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_view(request, 'library', 'NptReason', context)

def reasonForm(request, pk=None):
    fields = ('name', 'min_time', 'remote_num',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'library', 'NptReason', pk, fields)

def reasonDelete(request, pk):
    return dynamic_delete_view(request, 'library', 'NptReason', pk)