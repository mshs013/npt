from core.utils.views import dynamic_view, dynamic_form_view, dynamic_delete_view, dynamic_trashed_view, dynamic_restore_view
from django.forms.widgets import CheckboxSelectMultiple

# Create your views here.
def shift(request):
    list_display = ('sl', 'name', 'start_time', 'end_time', 'company', 'created_by', 'created_at', 'updated_by', 'updated_at',)
    default_sort = ['name', 'start_time', 'end_time', 'company']  # Default sorting by name ascending and created_at descending
    list_filter = ('name', 'start_time', 'end_time', 'company',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
        'per_page': 15,
    }
    
    return dynamic_view(request, 'library', 'Shift', context)

def shiftForm(request, pk=None):
    fields = ('name', 'start_time', 'end_time', 'company',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'library', 'Shift', pk, fields)

def shiftDelete(request, pk):
    return dynamic_delete_view(request, 'library', 'Shift', pk)

def shiftTrashed(request):
    list_display = ('sl', 'name', 'start_time', 'end_time', 'company', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'library', 'Shift', context)

def shiftRestore(request, pk):
    return dynamic_restore_view(request, 'library', 'Shift', pk)