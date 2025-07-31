from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django import forms
from django.utils import timezone
from django.contrib import messages
from django.db import models
from django.db.models.signals import post_save
from core.utils.utils import get_related_objects, get_model, apply_filters, paginate_queryset, get_display_value, apply_search, url_name_exists, get_simplified_field_name, get_related_fields
from core.forms import generate_dynamic_formset
from core.models import User
from core.signals import create_or_update_user_profile

def dynamic_multiform_view(request, app_label, head_model_name, pk=None, model_configs=None, hide_fields=None, readonly_fields=None, widget_overrides=None, is_form_row=True, extra_form=1):
    """
    A dynamic view for creating and updating models with related inline formsets using Crispy Forms.
    """
    instance = None
    title = 'Create ' + head_model_name
            
    if pk:
        HeadModel = get_model(app_label, head_model_name)
        instance = get_object_or_404(HeadModel, id=pk)
        title = 'Edit ' + head_model_name
        extra_form = 0

    head_form, body_formsets = generate_dynamic_formset(
        app_label,
        head_model_name,
        model_configs,
        instance=instance,
        hide_fields=hide_fields or [],
        readonly_fields=readonly_fields or [],
        widget_overrides=widget_overrides,
        is_form_row=is_form_row,
        extra_form=extra_form,
    )
    
    has_file_field = any(
        field.widget.input_type == 'file' for formset in body_formsets for field in formset['formset'].forms[0].fields.values()
    )

    # Add this before checking for 'Profile'
    #print("Model Configurations:", model_configs)

    # Check if 'Profile' is present
    profile_model_in_body_models = any(
        body_model['model_name'] == 'Profile'
        for body_model in model_configs['body_models']
    )
    #print("Profile Model in Body Models:", profile_model_in_body_models)

    if request.method == 'POST':
        head_form = head_form.__class__(request.POST, request.FILES, instance=instance)
        body_formsets_instances = [
            formset['formset'].__class__(request.POST, request.FILES, instance=instance) for formset in body_formsets
        ]

        if head_form.is_valid() and all([formset.is_valid() for formset in body_formsets_instances]):
            if profile_model_in_body_models:
                post_save.disconnect(create_or_update_user_profile, sender=User)

            saved_head = head_form.save(commit=False)

            # Handle password updates
            if 'password' in head_form.cleaned_data and head_form.cleaned_data['password']:
                saved_head.set_password(head_form.cleaned_data['password'])

            saved_head.save()
            if hasattr(head_form, 'save_m2m'):
                head_form.save_m2m()

            if profile_model_in_body_models:
                post_save.connect(create_or_update_user_profile, sender=User)

            # Save body formsets
            for body_formset in body_formsets_instances:
                instances = body_formset.save(commit=False)
                # Loop over each form in the formset
                for form in body_formset.forms:
                    # Handle forms that are marked for deletion
                    if form.cleaned_data.get('DELETE'):
                        if form.instance.pk:  # Ensure the instance exists in the database before trying to delete
                            form.instance.delete()
                    else:
                        # Save the instance if it's not marked for deletion
                        obj = form.instance
                        setattr(obj, body_formsets[0]['fk_field'], saved_head)  # Set the foreign key to the head instance
                        obj.save()  # Save the instance to the database

                body_formset.save_m2m()

            # Add a specific flash message based on whether the instance is new or being updated
            if pk:
                messages.success(request, f'{head_model_name} was updated successfully.')
            else:
                messages.success(request, f'{head_model_name} was created successfully.')

            return redirect(reverse(f'view_{head_model_name.lower()}'))  # Adjust with your success URL

    context = {
        'head_form': head_form,
        'body_formsets': body_formsets,
        'has_file_field': has_file_field,
        'is_form_row':is_form_row,
        'base_model_name': head_model_name,
        'view_url': f'view_{head_model_name.lower()}',
        'title': title,
        'pk': pk,
    }
    return render(request, 'core/dynamic_multiform.html', context)


def dynamic_view(request, app_name, model_name, context):
    """Dynamic list view with sorting and filtering options."""
    model = get_model(app_name, model_name)

    # Extract parameters from context
    list_display = context.get('list_display', [f.name for f in model._meta.fields])
    default_sort = context.get('default_sort', [])
    list_filter = context.get('list_filter', [])
    title = context.get('title', model._meta.verbose_name)

    # Get filter parameters and search query
    filters = {field: request.POST.get(field) for field in list_filter}
    search_query = request.POST.get('q', '')

    # Get sorting parameters
    sort_field = request.GET.get('sort')
    sort_order = request.GET.get('order', 'asc')
    valid_fields = [f.name for f in model._meta.fields]
    sort_field = sort_field if sort_field in valid_fields else None

    # Apply filters and search
    query_filters = apply_filters(model, filters)
    if search_query:
        search_fields = list_filter
        query_filters &= apply_search(model, search_query, search_fields)

    # Build the queryset with select_related and prefetch_related
    queryset = model.objects.filter(query_filters)

    # Get the related fields for your model
    select_related_fields, prefetch_related_fields = get_related_fields(model, list_display)
    
    # Apply select_related and prefetch_related
    queryset = queryset.select_related(*select_related_fields)
    queryset = queryset.prefetch_related(*prefetch_related_fields)
    
    total_count = queryset.count()  # Get the total count for pagination
    if sort_field:
        queryset = queryset.order_by(f'-{sort_field}' if sort_order == 'desc' else sort_field)
    elif default_sort:
        queryset = queryset.order_by(*default_sort)

    # Pagination
    object_list, paginator = paginate_queryset(request, queryset)
    

    url_remove = request.GET.urlencode().replace(f"sort={sort_field.lstrip('-')}&", "").replace(f"&order={sort_order}", "") if sort_field else ''
    # Prepare headers
    headers = [
        {
            'name': field,
            'sortable': field in valid_fields,
            'sorted': field == (sort_field.lstrip('-') if sort_field else None),
            'ascending': sort_order == 'asc',
            'url_primary': f'?sort={field}&order={"asc" if sort_order == "desc" else "desc"}' if field in valid_fields else '',
            'url_remove': f'?{url_remove}' if url_remove else '',
            'text': get_simplified_field_name(field),
        }
        for field in list_display
    ]

    # Check permissions
    def check_permission(action):
        return request.user.has_perm(f'{app_name}.{action}_{model_name.lower()}')

    permissions = {
        'can_add': check_permission('add'),
        'can_change': check_permission('change'),
        'can_delete': check_permission('delete'),
        'can_detailview': check_permission('detail'),
        'can_trashed': check_permission('trashed'),
    }

    # Prepare URLs for actions
    view_url_name = f'view_{model_name.lower()}'
    detail_url_name = f'detail_{model_name.lower()}'
    add_url_name = f'add_{model_name.lower()}'
    change_url_name = f'change_{model_name.lower()}'
    delete_url_name = f'delete_{model_name.lower()}'
    trashed_url_name = f'trashed_{model_name.lower()}'
    
    # Check action URLs
    detail_url = url_name_exists(detail_url_name, pk=1)  # Update with your actual pk logic
    add_url = url_name_exists(add_url_name)
    change_url = url_name_exists(change_url_name, pk=1)  # Update with your actual pk logic
    delete_url = url_name_exists(delete_url_name, pk=1)  # Update with your actual pk logic
    trashed_url = url_name_exists(trashed_url_name)

    # Prepare context
    context.update({
        'object_list': [
            {
                'fields': [
                    (
                        field,
                        i + 1 + (object_list.number - 1) * object_list.paginator.per_page  # For 'sl'
                        if field == 'sl' else get_display_value(obj, field)
                    )
                    for field in list_display
                ],
                'pk': obj.pk
            }
            for i, obj in enumerate(object_list)
        ],
        'headers': headers,
        'app_name': app_name,
        'model_name': model_name,
        'object_verbose_name_plural': model._meta.verbose_name_plural,
        'object_verbose_name': model._meta.verbose_name,
        'filters': request.POST,
        'total_count': total_count,
        'page_obj': object_list,
        'opts': model._meta,
        'title': title,
        **permissions,
        'list_display': list_display,
        'default_sort': default_sort,
        'list_filter': list_filter,
        'view_url_name': view_url_name,
        'detail_url_name': detail_url_name,
        'add_url_name': add_url_name,
        'change_url_name': change_url_name,
        'delete_url_name': delete_url_name,
        'trashed_url_name': trashed_url_name,
        'detail_url': detail_url,
        'add_url': add_url,
        'change_url': change_url,
        'delete_url': delete_url,
        'trashed_url': trashed_url,
    })

    return render(request, 'core/dynamic_list.html', context)



def dynamic_form_view(request, app_name, model_name, pk=None, fields=None, widget_overrides=None):
    """Dynamic form view (add or edit) with customizable fields."""
    model = get_model(app_name, model_name)
    form_class = forms.modelform_factory(model, fields=fields if fields else '__all__')

    if pk:
        instance = get_object_or_404(model, pk=pk)
        title = 'Edit ' + model._meta.verbose_name
    else:
        instance = None
        title = 'Create ' + model._meta.verbose_name

    form = form_class(request.POST or None, request.FILES or None, instance=instance)

    # Apply widget overrides
    if widget_overrides:
        for field_name, widget in widget_overrides.items():
            if field_name in form.fields:
                # Apply widget with choices if it is a MultipleChoiceField
                field = form.fields[field_name]
                if isinstance(field, forms.ModelMultipleChoiceField) or isinstance(field, forms.MultipleChoiceField):
                    # Apply widget with choices if it is a MultipleChoiceField
                    form.fields[field_name].widget = widget(choices=field.choices)
                else:
                    form.fields[field_name].widget = widget

    has_file_field = any(isinstance(field.widget, forms.ClearableFileInput) for field in form.fields.values())

    if request.method == 'POST':
        if form.is_valid():
            instance = form.save(commit=False)

            # Get the model class
            model_class = instance.__class__

            # Check if the fields exist on the model
            fields = [f.name for f in model_class._meta.get_fields()]

            # Set created_by and created_at fields if they exist
            if 'created_by' in fields and 'created_at' in fields:
                if not instance.id:  # New instance
                    instance.created_by = request.user
                    instance.created_at = timezone.now()

            # Set updated_by and updated_at fields if they exist
            if 'updated_by' in fields and 'updated_at' in fields:
                if instance.id:  # Existing instance
                    instance.updated_by = request.user
                    instance.updated_at = timezone.now()
                    
            instance.save()

            # Add a specific flash message based on whether the instance is new or being updated
            if pk:
                messages.success(request, f'{model._meta.verbose_name} was updated successfully.')
            else:
                messages.success(request, f'{model._meta.verbose_name} was created successfully.')

            return redirect(reverse(f'view_{model_name.lower()}'))
        else:
            messages.error(request, 'Please correct the errors below.')

    context = {
        'form': form,
        'model_name': model_name,
        'object': instance,
        'title': title,
        'opts': model._meta,
        'has_file_field': has_file_field,
        'view_url':f'view_{model_name.lower()}',
    }
    return render(request, 'core/dynamic_form.html', context)


def dynamic_delete_view(request, app_name, model_name, pk):
    """Dynamic delete confirmation view with multi-layered related objects information."""
    model = get_model(app_name, model_name)
    obj = get_object_or_404(model, pk=pk)

    #deleted_objects = [str(obj)]  # Or use a method to format the objects
    #print(f'Meta: {obj._meta.related_objects}')
    related_objects, model_count = get_related_objects(obj, request)
    #print(f'Meta: {model_count}')
    #print(f'Meta: {related_objects}')

    object_name = str(obj)
    verbose_name = model._meta.verbose_name
    verbose_name_plural = model._meta.verbose_name_plural

    if request.method == "POST":
        obj.delete()
        # Add a specific flash message
        messages.success(request, f'{model._meta.verbose_name} was deleted successfully.')

        return redirect(reverse(f'view_{model_name.lower()}'))

    context = {
        'object': obj,
        'object_name': object_name,
        'verbose_name': verbose_name,
        'verbose_name_plural': verbose_name_plural,
        'related_objects': related_objects,
        'model_count': model_count,
        'opts': model._meta,
        'view_link': f'view_{model_name.lower()}',
        'change_link': f'change_{model_name.lower()}',
        'title':'Are you sure?',
    }
    return render(request, 'core/dynamic_confirm_delete.html', context)



def dynamic_detail_view(request, app_name, model_name, pk, list_display=None):
    """Dynamic detail view with customizable fields to display."""
    model = get_model(app_name, model_name)
    obj = get_object_or_404(model, pk=pk)

    if list_display is None:
        list_display = [field.name for field in model._meta.fields]  # Default to all fields

    # Use the get_display_value function to prepare field values
    field_values = {field: get_display_value(obj, field) for field in list_display}
    view_url_name = f'view_{model_name.lower()}'
    title = 'Detail ' + model._meta.verbose_name

    context = {
        'object': obj,
        'fields': field_values,
        'view_url':view_url_name,
        'opts': model._meta,
        'title':title,
    }
    return render(request, 'core/dynamic_detail.html', context)

def dynamic_trashed_view(request, app_name, model_name, context):
    """Dynamic list view for trashed items with sorting and filtering options."""
    model = get_model(app_name, model_name)

    # Extract parameters from context
    list_display = context.get('list_display', [f.name for f in model._meta.fields])
    default_sort = context.get('default_sort', [])
    list_filter = context.get('list_filter', [])
    title = context.get('title', f"Trashed {model._meta.verbose_name}")

    # Get filter parameters
    filters = {field: request.POST.get(field, None) for field in list_filter}

    # Get search parameters
    search_query = request.POST.get('q', '')

    # Get sorting parameters
    sort_field = request.GET.get('sort', None)
    sort_order = request.GET.get('order', 'asc')  # Default to ascending
    valid_fields = [f.name for f in model._meta.fields]

    if sort_field not in valid_fields:
        sort_field = None

    # Apply filters and search
    query_filters = apply_filters(model, filters)

    # Apply search filter
    if search_query:
        search_fields = list_filter  # or a specific list of fields you want to search in
        query_filters &= apply_search(model, search_query, search_fields)

    # Apply filters and sorting
    queryset = model.deleted_objects.filter(query_filters)
    total_count = queryset.count()  # Get the total count for pagination
    if sort_field:
        queryset = queryset.order_by(f'-{sort_field}' if sort_order == 'desc' else sort_field)
    elif default_sort:
        queryset = queryset.order_by(*default_sort)

    # Pagination
    object_list, paginator = paginate_queryset(request, queryset)

    # Prepare headers
    headers = []
    for field in list_display:
        sortable = field in valid_fields
        sorted = field == (sort_field.lstrip('-') if sort_field else None)
        url_primary = f'?sort={field}&order={"asc" if sort_order == "desc" else "desc"}' if sortable else ''
        url_remove = request.GET.urlencode()
        if sort_field:
            url_remove = url_remove.replace(f'sort={sort_field.lstrip("-")}&', '').replace(f'&order={sort_order}', '')
        headers.append({
            'name': field,
            'sortable': sortable,
            'sorted': sorted,
            'ascending': sort_order == 'asc',
            'url_primary': url_primary,
            'url_remove': f'?{url_remove}' if url_remove else '',
            'text': field
        })

    # URLs for actions
    view_url_name = f'view_{model_name.lower()}'
    restore_url_name = f'restore_{model_name.lower()}'

    # Check permissions
    can_restore = request.user.has_perm(f'{app_name}.restore_{model_name.lower()}')
    can_view = request.user.has_perm(f'{app_name}.view_{model_name.lower()}')

    # Prepare context
    context.update({
        'object_list': [{
            'fields': [(field, get_display_value(obj, field)) for field in list_display],
            'pk': obj.pk
        } for obj in object_list],
        'headers': headers,
        'app_name': app_name,
        'model_name': model_name,
        'object_verbose_name_plural': model._meta.verbose_name_plural,
        'object_verbose_name': model._meta.verbose_name,
        'view_url_name':view_url_name,
        'restore_url_name': restore_url_name,
        'filters': request.POST,  # Pass filters for the template
        'can_view': can_view,
        'can_restore': can_restore,
        'list_display': list_display,  # Pass list_display for template use
        'default_sort': default_sort,  # Pass default_sort for template use
        'list_filter': list_filter,  # Pass list_filter for template use
        'total_count': total_count,  # Total count of all rows
        'page_obj': object_list,
        'opts': model._meta,
        'title': title,
    })

    return render(request, 'core/dynamic_trashed_list.html', context)

def dynamic_restore_view(request, app_name, model_name, pk):
    """Dynamic restore confirmation view with multi-layered related objects information."""
    model = get_model(app_name, model_name)
    obj = get_object_or_404(model.deleted_objects, pk=pk)

    related_objects, model_count = get_related_objects(obj, request)

    object_name = str(obj)
    verbose_name = model._meta.verbose_name
    verbose_name_plural = model._meta.verbose_name_plural

    if request.method == "POST":
        obj.restore()
        messages.success(request, f'{model._meta.verbose_name} was restored successfully.')
        return redirect(reverse(f'view_{model_name.lower()}'))

    context = {
        'object': obj,
        'object_name': object_name,
        'verbose_name': verbose_name,
        'verbose_name_plural': verbose_name_plural,
        'related_objects': related_objects,
        'model_count': model_count,
        'opts': model._meta,
        'view_link': f'view_{model_name.lower()}',
        'change_link': f'change_{model_name.lower()}',
        'title': 'Are you sure you want to restore?',
    }
    return render(request, 'core/dynamic_confirm_restore.html', context)
