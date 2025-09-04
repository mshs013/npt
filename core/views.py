from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.forms.widgets import CheckboxSelectMultiple
from core.models import User
from core.forms import DynamicUserProfileForm
from core.utils.views import dynamic_view, dynamic_form_view, dynamic_delete_view, dynamic_trashed_view, dynamic_restore_view, dynamic_detail_view, dynamic_multiform_view
from core.utils.utils import get_user_machines

# Create your views here.
def permission_denied_view(request, exception=None):
    context = {
        'status' : 403,
        'title' : "403 - Forbidden"
    }
    return render(request, "core/403.html", context)

def page_not_found_view(request, exception=None):
    context = {
        'status' : 404,
        'title' : "404 - Page Not Found"
    }
    return render(request, "core/404.html", context)

def server_error_view(request):
    context = {
        'status' : 500,
        'title' : "500 - Server Error"
    }
    return render(request, "core/500.html", context)

def menu(request):
    list_display = ('name', 'parent', 'url', 'order', 'permission',)
    default_sort = ['-parent', 'order']  # Default sorting by name ascending and created_at descending
    list_filter = ('name', 'parent', 'url',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_view(request, 'core', 'Menu', context)

def menuForm(request, pk=None):
    fields = ('name', 'parent', 'url', 'icon', 'order', 'permission',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'core', 'Menu', pk, fields)

def menuDelete(request, pk):
    return dynamic_delete_view(request, 'core', 'Menu', pk)

def activitylog(request):
    list_display = ('actor', 'action_type', 'action_time', 'status', 'content_type')
    default_sort = ['-action_time']  # Default sorting by name ascending and created_at descending
    list_filter = ('action_type', 'status')  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_view(request, 'core', 'ActivityLog', context)

def activitylogDetail(request, pk):
    #list_display = ('name', 'abv', 'address', 'factories', 'email', 'phone', 'fax', 'website', 'logo', 'is_kanban',)  # Specify fields to display
    return dynamic_detail_view(request, 'core', 'ActivityLog', pk)

def user(request):
    list_display = ('email', 'full_name', 'profile__user_img', 'profile__department', 'profile__designation', 'is_superuser', 'is_staff', 'is_active', 'last_login')
    default_sort = ['email']  # Default sorting by name ascending and created_at descending
    list_filter = ("first_name", "last_name", 'profile__department', 'profile__designation', "is_staff", "is_active",)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_view(request, 'core', 'User', context)

def userForm(request, pk=None):
    instance = get_object_or_404(User, pk=pk) if pk else None

    if request.method == 'POST':
        form = DynamicUserProfileForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save(commit=True)  # save User + Profile but not M2M yet

            messages.success(request, 'User saved successfully.')
            return redirect('view_user')
    else:
        form = DynamicUserProfileForm(instance=instance)

    title = "Edit User" if instance else "Add User"
    context = {
        'form': form,
        'instance': instance,
        'title': title,
    }
    return render(request, 'core/dynamic_user_form.html', context)

def userDelete(request, pk):
    return dynamic_delete_view(request, 'core', 'User', pk)

def department(request):
    list_display = ('sl', 'name', 'created_by', 'created_at', 'updated_by', 'updated_at',)
    default_sort = ['name']  # Default sorting by name ascending and created_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_view(request, 'core', 'Department', context)

def departmentForm(request, pk=None):
    fields = ('name',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'core', 'Department', pk, fields)

def departmentDelete(request, pk):
    return dynamic_delete_view(request, 'core', 'Department', pk)

def departmentTrashed(request):
    list_display = ('sl', 'name', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'core', 'Department', context)

def departmentRestore(request, pk):
    return dynamic_restore_view(request, 'core', 'Department', pk)

def designation(request):
    list_display = ('sl', 'name', 'created_by', 'created_at', 'updated_by', 'updated_at',)
    default_sort = ['name']  # Default sorting by name ascending and created_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_view(request, 'core', 'Designation', context)

def designationForm(request, pk=None):
    fields = ('name',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'core', 'Designation', pk, fields)

def designationDelete(request, pk):
    return dynamic_delete_view(request, 'core', 'Designation', pk)

def designationTrashed(request):
    list_display = ('sl', 'name', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'core', 'Designation', context)

def designationRestore(request, pk):
    return dynamic_restore_view(request, 'core', 'Designation', pk)

def reason(request):
    list_display = ('sl', 'name', 'min_time', 'remote_num', 'color', 'created_by', 'created_at', 'updated_by', 'updated_at',)
    default_sort = ['remote_num']  # Default sorting by name ascending and created_at descending
    list_filter = ('name', 'min_time', 'remote_num')  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
        'per_page': 15,
    }
    
    return dynamic_view(request, 'core', 'NptReason', context)

def reasonForm(request, pk=None):
    fields = ('name', 'min_time', 'remote_num', 'color',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'core', 'NptReason', pk, fields)

def reasonDelete(request, pk):
    return dynamic_delete_view(request, 'core', 'NptReason', pk)

def reasonTrashed(request):
    list_display = ('sl', 'name', 'min_time', 'remote_num', 'color', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name', 'min_time', 'remote_num')  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'core', 'NptReason', context)

def reasonRestore(request, pk):
    return dynamic_restore_view(request, 'core', 'NptReason', pk)

def brand(request):
    list_display = ('sl', 'name', 'created_by', 'created_at', 'updated_by', 'updated_at',)
    default_sort = ['name']  # Default sorting by name ascending and created_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
        'per_page': 15,
    }
    
    return dynamic_view(request, 'core', 'Brand', context)

def brandForm(request, pk=None):
    fields = ('name',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'core', 'Brand', pk, fields)

def brandDelete(request, pk):
    return dynamic_delete_view(request, 'core', 'Brand', pk)

def brandTrashed(request):
    list_display = ('sl', 'name', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'core', 'Brand', context)

def brandRestore(request, pk):
    return dynamic_restore_view(request, 'core', 'Brand', pk)

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
    
    return dynamic_view(request, 'core', 'Company', context)

def companyForm(request, pk=None):
    fields = ('name',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'core', 'Company', pk, fields)

def companyDelete(request, pk):
    return dynamic_delete_view(request, 'core', 'Company', pk)

def companyTrashed(request):
    list_display = ('sl', 'name', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'core', 'Company', context)

def companyRestore(request, pk):
    return dynamic_restore_view(request, 'core', 'Company', pk)

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
    
    return dynamic_view(request, 'core', 'Building', context)

def buildingForm(request, pk=None):
    fields = ('name', 'company',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'core', 'Building', pk, fields)

def buildingDelete(request, pk):
    return dynamic_delete_view(request, 'core', 'Building', pk)

def buildingTrashed(request):
    list_display = ('sl', 'name', 'company', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'core', 'Building', context)

def buildingRestore(request, pk):
    return dynamic_restore_view(request, 'core', 'Building', pk)

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
    
    return dynamic_view(request, 'core', 'Floor', context)

def floorForm(request, pk=None):
    fields = ('name', 'building',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'core', 'Floor', pk, fields)

def floorDelete(request, pk):
    return dynamic_delete_view(request, 'core', 'Floor', pk)

def floorTrashed(request):
    list_display = ('sl', 'name', 'building', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'core', 'Floor', context)

def floorRestore(request, pk):
    return dynamic_restore_view(request, 'core', 'Floor', pk)

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
    
    return dynamic_view(request, 'core', 'Block', context)

def blockForm(request, pk=None):
    fields = ('name', 'floor',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'core', 'Block', pk, fields)

def blockDelete(request, pk):
    return dynamic_delete_view(request, 'core', 'Block', pk)

def blockTrashed(request):
    list_display = ('sl', 'name', 'floor', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'core', 'Block', context)

def blockRestore(request, pk):
    return dynamic_restore_view(request, 'core', 'Block', pk)

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
    
    return dynamic_view(request, 'core', 'MachineType', context)

def machinetypeForm(request, pk=None):
    fields = ('name',)  # Specify fields to include in the form
    return dynamic_form_view(request, 'core', 'MachineType', pk, fields)

def machinetypeDelete(request, pk):
    return dynamic_delete_view(request, 'core', 'MachineType', pk)

def machinetypeTrashed(request):
    list_display = ('sl', 'name', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  # Default sorting by name ascending and deleted_at descending
    list_filter = ('name',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'core', 'MachineType', context)

def machinetypeRestore(request, pk):
    return dynamic_restore_view(request, 'core', 'MachineType', pk)

def machine(request):
    machine = get_user_machines(request.user)
    print(machine)
    list_display = ('sl', 'mc_no', 'brand', 'model', 'category', 'block', 'block__floor__building__company', 'created_by', 'created_at', 'updated_by', 'updated_at',)
    default_sort = ['mc_no']  
    list_filter = ('mc_no', 'brand', 'model', 'category', 'block',)  

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
        'per_page': 15,
        'pre_filter': {
            'id__in': get_user_machines(request.user)
        }
    }
    
    return dynamic_view(request, 'core', 'Machine', context)

def machineForm(request, pk=None):
    fields = ('mc_no', 'device_mc', 'brand', 'model', 'category', 'dia', 'feeder', 'shinker', 'track', 'max_rpm', 'gg', 'speed_factor', 'extra_cylinder', 'lycra_attach', 'block', 'mc_types',)  # Specify fields to include in the form
    readonly_fields = ['device_mc']  # Make email read-only in edit mode
    widget_overrides = {
        'mc_types': CheckboxSelectMultiple,
    }
    return dynamic_form_view(request, 'core', 'Machine', pk, fields, widget_overrides, readonly_fields)

def machineDelete(request, pk):
    return dynamic_delete_view(request, 'core', 'Machine', pk)

def machineTrashed(request):
    list_display = ('sl', 'mc_no', 'brand', 'model', 'category', 'block', 'deleted_by', 'deleted_at',)
    default_sort = ['-deleted_at']  
    list_filter = ('mc_no', 'brand', 'model', 'category', 'block',)  

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
    }
    
    return dynamic_trashed_view(request, 'core', 'Machine', context)

def machineRestore(request, pk):
    return dynamic_restore_view(request, 'core', 'Machine', pk)
    
### NPT Log
def npt(request):
    list_display = ('sl', 'machine', 'reason', 'off_time', 'on_time', 'get_duration',)
    default_sort = ['machine', '-on_time']  # Default sorting by name ascending and created_at descending
    list_filter = ('machine', 'reason',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
        'per_page' : 50,
    }
    
    return dynamic_view(request, 'core', 'ProcessedNPT', context)

### Rotation Log
def rotation(request):
    list_display = ('sl', 'machine', 'count', 'count_time',)
    default_sort = ['machine', '-count_time']  # Default sorting by name ascending and created_at descending
    list_filter = ('machine',)  # Filters to include in the form

    context = {
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
        'per_page' : 50,
    }
    
    return dynamic_view(request, 'core', 'RotationStatus', context)
