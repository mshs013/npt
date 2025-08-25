from core.utils.views import dynamic_view, dynamic_form_view, dynamic_delete_view, dynamic_trashed_view, dynamic_restore_view, dynamic_detail_view, dynamic_multiform_view
from django.forms.widgets import CheckboxSelectMultiple

# Create your views here.
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

    model_configs = {
        'head_fields': ['first_name', 'last_name', 'email', 'password', 'is_active', 'is_staff', 'user_permissions'],
        'body_models': [
            {
                'model_name': 'Profile',
                'fields': ['official_id', 'contact_no', 'department', 'designation', 'user_img', 'user_sign'],
                'fk_field': 'user',
            }
        ]
    }
    
    hide_fields = ['password']  # Hide password field in edit form
    readonly_fields = ['email']  # Make email read-only in edit mode
    widget_overrides = {
        'user_permissions': CheckboxSelectMultiple(),
    }

    return dynamic_multiform_view(
        request,
        app_label='core',
        head_model_name='User',
        pk=pk,
        model_configs=model_configs,
        hide_fields=hide_fields,
        readonly_fields=readonly_fields,
        widget_overrides=widget_overrides,
        is_form_row=False,
        extra_form=1,
    )

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