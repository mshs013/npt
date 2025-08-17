from core.utils.views import dynamic_view, dynamic_form_view, dynamic_delete_view, dynamic_trashed_view, dynamic_restore_view
from library.models import ProcessedNPT
from django.shortcuts import render

# Create your views here.
def reason(request):
    list_display = ('sl', 'name', 'min_time', 'remote_num', 'created_by', 'created_at', 'updated_by', 'updated_at',)
    default_sort = ['remote_num']  # Default sorting by name ascending and created_at descending
    list_filter = ('name', 'min_time', 'remote_num')  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
        'per_page': 15,
    }
    
    return dynamic_view(request, 'library', 'NptReason', context)

def reasonForm(request, pk=None):
    fields = ('name', 'min_time', 'remote_num',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'library', 'NptReason', pk, fields)

def reasonDelete(request, pk):
    return dynamic_delete_view(request, 'library', 'NptReason', pk)

def reasonTrashed(request):
    list_display = ('sl', 'name', 'min_time', 'remote_num', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name', 'min_time', 'remote_num')  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'library', 'NptReason', context)

def reasonRestore(request, pk):
    return dynamic_restore_view(request, 'library', 'NptReason', pk)

def npt(request):
    list_display = ('sl', 'mc_no', 'reason', 'off_time', 'on_time', 'get_duration',)
    default_sort = ['mc_no', '-on_time']  # Default sorting by name ascending and created_at descending
    list_filter = ('mc_no', 'reason',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_view(request, 'library', 'ProcessedNPT', context)

def rotation(request):
    list_display = ('sl', 'mc_no', 'count', 'count_time',)
    default_sort = ['mc_no', '-count_time']  # Default sorting by name ascending and created_at descending
    list_filter = ('mc_no',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_view(request, 'library', 'RotationStatus', context)

def company(request):
    list_display = ('sl', 'name', 'created_by', 'created_at', 'updated_by', 'updated_at',)
    default_sort = ['name']  # Default sorting by name ascending and created_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
        'per_page': 15,
    }
    
    return dynamic_view(request, 'library', 'Company', context)

def companyForm(request, pk=None):
    fields = ('name',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'library', 'Company', pk, fields)

def companyDelete(request, pk):
    return dynamic_delete_view(request, 'library', 'Company', pk)

def companyTrashed(request):
    list_display = ('sl', 'name', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'library', 'Company', context)

def companyRestore(request, pk):
    return dynamic_restore_view(request, 'library', 'Company', pk)

def building(request):
    list_display = ('sl', 'name', 'company', 'created_by', 'created_at', 'updated_by', 'updated_at',)
    default_sort = ['name', 'company']  # Default sorting by name ascending and created_at descending
    list_filter = ('name', 'company',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
        'per_page': 15,
    }
    
    return dynamic_view(request, 'library', 'Building', context)

def buildingForm(request, pk=None):
    fields = ('name', 'company',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'library', 'Building', pk, fields)

def buildingDelete(request, pk):
    return dynamic_delete_view(request, 'library', 'Building', pk)

def buildingTrashed(request):
    list_display = ('sl', 'name', 'company', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'library', 'Building', context)

def buildingRestore(request, pk):
    return dynamic_restore_view(request, 'library', 'Building', pk)

def floor(request):
    list_display = ('sl', 'name', 'building', 'created_by', 'created_at', 'updated_by', 'updated_at',)
    default_sort = ['name', 'building']  # Default sorting by name ascending and created_at descending
    list_filter = ('name', 'building',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
        'per_page': 15,
    }
    
    return dynamic_view(request, 'library', 'Floor', context)

def floorForm(request, pk=None):
    fields = ('name', 'building',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'library', 'Floor', pk, fields)

def floorDelete(request, pk):
    return dynamic_delete_view(request, 'library', 'Floor', pk)

def floorTrashed(request):
    list_display = ('sl', 'name', 'building', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'library', 'Floor', context)

def floorRestore(request, pk):
    return dynamic_restore_view(request, 'library', 'Floor', pk)

def block(request):
    list_display = ('sl', 'name', 'floor', 'created_by', 'created_at', 'updated_by', 'updated_at',)
    default_sort = ['name', 'floor']  # Default sorting by name ascending and created_at descending
    list_filter = ('name', 'floor',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
        'per_page': 15,
    }
    
    return dynamic_view(request, 'library', 'Block', context)

def blockForm(request, pk=None):
    fields = ('name', 'floor',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'library', 'Block', pk, fields)

def blockDelete(request, pk):
    return dynamic_delete_view(request, 'library', 'Block', pk)

def blockTrashed(request):
    list_display = ('sl', 'name', 'floor', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'library', 'Block', context)

def blockRestore(request, pk):
    return dynamic_restore_view(request, 'library', 'Block', pk)

def machinetype(request):
    list_display = ('sl', 'name', 'created_by', 'created_at', 'updated_by', 'updated_at',)
    default_sort = ['name']  # Default sorting by name ascending and created_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
        'per_page': 15,
    }
    
    return dynamic_view(request, 'library', 'MachineType', context)

def machinetypeForm(request, pk=None):
    fields = ('name',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'library', 'MachineType', pk, fields)

def machinetypeDelete(request, pk):
    return dynamic_delete_view(request, 'library', 'MachineType', pk)

def machinetypeTrashed(request):
    list_display = ('sl', 'name', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'library', 'MachineType', context)

def machinetypeRestore(request, pk):
    return dynamic_restore_view(request, 'library', 'MachineType', pk)

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