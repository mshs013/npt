from django.urls import NoReverseMatch, reverse
from django.db.models.deletion import Collector
from django.db import router, models
from collections import defaultdict
from django.utils.text import capfirst
from django.utils.html import format_html
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.exceptions import FieldDoesNotExist
from django.apps import apps
from django.db.models import Q, ForeignKey, CharField, ImageField, BooleanField, ManyToManyField, JSONField, DateTimeField, OneToOneRel, ManyToManyField, OneToOneField, ForeignKey
from django.core.files.images import ImageFile
from core.models import Profile
from datetime import datetime
from django.conf import settings
import os

QUOTE_MAP = {i: "_%02X" % i for i in b'":/_#?;@&=+$,"[]<>%\n\\'}

def paginate_queryset(request, queryset, per_page=10):
    """Paginate a queryset."""
    paginator = Paginator(queryset, per_page)
    page = request.POST.get('page') or request.GET.get('page')
    try:
        objects = paginator.page(page)
    except PageNotAnInteger:
        objects = paginator.page(1)
    except EmptyPage:
        objects = paginator.page(paginator.num_pages)
    return objects, paginator

def get_model(app_name, model_name):
    """Retrieve the model class dynamically."""
    return apps.get_model(app_name, model_name)

def get_simplified_field_name(field):
    """Dynamically remove everything before the last '__' in a field name."""
    return field.split('__')[-1]

def get_field_object_and_value(obj, field_path):
    """
    Traverse the field path to get the final field object and its value.
    :param obj: The instance of the model.
    :param field_path: The field path (e.g., 'profile__user_img').
    :return: Tuple (field_object, field_value) or (None, None) if not found.
    """
    field_parts = field_path.split('__')
    current_obj = obj

    for part in field_parts:
        try:
            field_object = current_obj._meta.get_field(part)
            
            if isinstance(field_object, (ForeignKey, OneToOneField)):
                # Move into the related object (forward relation)
                current_obj = getattr(current_obj, part, None)
                if not current_obj:
                    return None, None
            elif isinstance(field_object, OneToOneRel):
                # Handle reverse relation (e.g., profile__user_img)
                current_obj = getattr(current_obj, field_object.get_accessor_name(), None)
                if not current_obj:
                    return None, None
            else:
                # If it's the final part, return both field_object and its value
                return field_object, getattr(current_obj, part, None)
        except FieldDoesNotExist:
            return None, None

    # If we reach here, current_obj is the related model instance itself (e.g., 'profile')
    # Return the field object as the model's `__str__()` method and the related object itself
    return current_obj.__class__.__name__, str(current_obj) if current_obj else None

def get_special_fields():
    """
    Return a tuple of fields to skip when processing related fields.

    Returns:
        tuple: A tuple of field names to skip.
    """
    return ('created_info', 'updated_info', 'deleted_info', 'actor', 'full_name')

def get_display_value(obj, field):
    """Get display value for a field, including composite fields and foreign keys."""
    special_fields = get_special_fields()
    # Skip specific fields like 'created_info'
    if field in special_fields:
        if field == 'created_info':
            return format_html('{} <small class="d-block">[{}]</small>', obj.created_by.get_full_name(), obj.created_at.strftime("%d-%b-%Y %I:%M:%S %p"))
        elif field == 'updated_info':
            if obj.updated_by:
                return format_html('{} <small class="d-block">[{}]</small>', obj.updated_by.get_full_name(), obj.updated_at.strftime("%d-%b-%Y %I:%M:%S %p"))
            else:
                return ''
        elif field == 'deleted_info':
            if obj.deleted_by:
                return format_html('{} <small class="d-block">[{}]</small>', obj.deleted_by.get_full_name(), obj.deleted_at.strftime("%d-%b-%Y %I:%M:%S %p"))
            else:
                return ''
        elif field == 'actor':
            if obj.actor:
                return obj.actor.get_full_name()
            else:
                return ''
        elif field == 'full_name':
           return obj.get_full_name()

    
    # Retrieve the field object using get_field_object
    field_object, field_value = get_field_object_and_value(obj, field)
    
    if not field_object:
        return ''
        
    # Handle field types based on the retrieved field object
    if isinstance(field_object, ImageField):
        if field_value and os.path.isfile(os.path.join(settings.MEDIA_ROOT, str(field_value))):
            image_url = field_value.url
            return format_html('<img src="{}" alt="Image" style="width: 100px; height: auto;">', image_url)
        else:
            return ''
    elif isinstance(field_object, BooleanField):
        return 'Yes' if field_value else 'No'
    elif isinstance(field_object, (ForeignKey, OneToOneField)):
        return str(field_value) if field_value else ''
    elif isinstance(field_object, OneToOneRel):
        # Handle reverse relation objects
        return str(field_value) if field_value else ''
    elif isinstance(field_object, ManyToManyField):
        related_objects = field_value.all() if field_value else []
        if related_objects:
            return ', '.join([str(related_object) for related_object in related_objects])
        else:
            return ''
    elif isinstance(field_object, JSONField):
        return format_json_as_html_list(field_value) if field_value else ''
    elif isinstance(field_object, DateTimeField):
        return field_value.strftime("%d-%b-%Y %I:%M:%S %p") if field_value else ''

    # General case for other fields
    return field_value if field_value else ''

def get_related_fields(model, list_display):
    """
    Generate select_related and prefetch_related fields for a given model,
    while skipping specified fields.

    Args:
        model: The Django model class to inspect.
        list_display: List of fields to include from the display.
        fields_to_skip: Set of field names to skip (optional).

    Returns:
        tuple: A tuple containing two lists: select_related_fields and prefetch_related_fields.
    """
    fields_to_skip = get_special_fields()

    # Get all relation fields
    related_fields = [f for f in model._meta.get_fields() if f.is_relation]
    
    select_related_fields = set()  # Use set to ensure uniqueness
    prefetch_related_fields = set()  # Use set to ensure uniqueness

    def add_nested_fields(field_name):
        parts = field_name.split('__')
        current_model = model

        # Iterate through each part in the nested field path
        for i, part in enumerate(parts):
            try:
                # Get the field from the current model
                related_field = current_model._meta.get_field(part)

                # Check if it's a ForeignKey, OneToOneField, or OneToOneRel
                if isinstance(related_field, (models.ForeignKey, models.OneToOneField, models.OneToOneRel)):
                    # Add the field to select_related_fields
                    select_related_fields.add('__'.join(parts[:i + 1]))

                    # Move to the related model for further nesting, except for reverse relations (OneToOneRel)
                    if not isinstance(related_field, models.OneToOneRel):
                        current_model = related_field.related_model

                elif isinstance(related_field, models.ManyToManyField):
                    # Add to prefetch_related_fields
                    prefetch_related_fields.add('__'.join(parts[:i + 1]))
                    break  # Stop processing for ManyToMany fields

            except FieldDoesNotExist:
                return  # Skip if the field doesn't exist

    # Iterate through direct related fields in the model
    for field in related_fields:
        if field.name not in fields_to_skip:
            if isinstance(field, models.ForeignKey):
                select_related_fields.add(field.name)
            elif isinstance(field, (models.OneToOneField, models.ManyToManyField)):
                prefetch_related_fields.add(field.name)

            # Handle subchild fields for ForeignKey and OneToOneField
            if isinstance(field, (models.ForeignKey, models.OneToOneField)) and hasattr(field, 'related_model'):
                for sub_field in field.related_model._meta.get_fields():
                    if isinstance(sub_field, models.ForeignKey) or isinstance(sub_field, models.OneToOneField):
                        select_related_fields.add(f"{field.name}__{sub_field.name}")
                    elif isinstance(sub_field, models.ManyToManyField):
                        prefetch_related_fields.add(f"{field.name}__{sub_field.name}")

    # Add fields for select_related and prefetch_related from list_display
    for field in list_display:
        if field not in fields_to_skip:
            add_nested_fields(field)

    # Convert sets back to lists before returning
    return list(select_related_fields), list(prefetch_related_fields)


def get_filter_choices(model, field_name):
    """Return choices for a filter field, handling ForeignKey and regular fields."""
    try:
        field = model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return []

    # Handle ForeignKey fields
    if isinstance(field, ForeignKey):
        related_model = field.related_model
        # Return a list of tuples with primary key and string representation
        return [(obj.pk, str(obj)) for obj in related_model.objects.all()]

    # Handle fields with choices
    if hasattr(field, 'choices') and field.choices:
        return [(choice[0], choice[1]) for choice in field.choices]

    # Handle CharField or TextField (custom value extraction)
    if isinstance(field, CharField):
        return [(value, value) for value in model.objects.values_list(field_name, flat=True).distinct()]

    return []

def apply_filters(model, filters):
    """Apply filters to a queryset."""
    query_filters = Q()
    for field, value in filters.items():
        if value:
            try:
                field_instance = model._meta.get_field(field)
                if isinstance(field_instance, ForeignKey):
                    query_filters &= Q(**{f'{field}__id__exact': value})
                else:
                    query_filters &= Q(**{f'{field}__icontains': value})
            except FieldDoesNotExist:
                pass
    return query_filters

def apply_search(model, search_query, search_fields):
    """Apply search to a queryset."""
    search_filters = Q()
    for field in search_fields:
        try:
            field_instance = model._meta.get_field(field)
            if isinstance(field_instance, ForeignKey):
                related_model = field_instance.related_model
                if related_model == Profile:
                    # Special handling for Profile model
                    # Search within User model fields related to Profile
                    related_fields = ['user__first_name', 'user__last_name']
                    for related_field in related_fields:
                        search_filters |= Q(**{f'{field}__{related_field}__icontains': search_query})
                else:
                    if hasattr(related_model, 'name'):
                        search_filters |= Q(**{f'{field}__name__icontains': search_query})
                    else:
                        related_fields = ['first_name', 'last_name']  # Adjust if necessary
                        for related_field in related_fields:
                            if hasattr(related_model, related_field):
                                search_filters |= Q(**{f'{field}__{related_field}__icontains': search_query})
            else:
                search_filters |= Q(**{f'{field}__icontains': search_query})
        except FieldDoesNotExist:
            pass
    return search_filters

def get_related_objects(obj, request):
    """
    Find all objects related to ``objs`` that should also be deleted. ``objs``
    must be a homogeneous iterable of objects (e.g. a QuerySet).

    Return a nested list of strings suitable for display in the
    template with the ``unordered_list`` filter.
    """
    try:
        objs = [obj]
    except IndexError:
        return [], {}, set(), []
    else:
        using = router.db_for_write(obj._meta.model)
    collector = NestedObjects(using=using, origin=objs)
    collector.collect(objs)

    def format_callback(obj):
        model = obj.__class__
        opts = obj._meta

        no_edit_link = "%s: %s" % (capfirst(opts.verbose_name), obj)

        if request.user.has_perm(f'{opts.app_label}.change_{opts.model_name}'):
            
            try:
                admin_url = reverse(
                    "change_%s"
                    % (opts.model_name),
                    None,
                    (quote(obj.pk),),
                )
            except NoReverseMatch:
                # Change url doesn't exist -- don't display link to edit
                return no_edit_link

            # Display a link to the admin page.
            return format_html(
                '{}: <a href="{}">{}</a>', capfirst(opts.verbose_name), admin_url, obj
            )
        else:
            # Don't display link to edit, because it either has no
            # admin or is edited inline.
            return no_edit_link

    to_delete = collector.nested(format_callback)

    model_count = {
        model._meta.verbose_name_plural: len(objs)
        for model, objs in collector.model_objs.items()
    }

    return to_delete, model_count

class NestedObjects(Collector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.edges = {}  # {from_instance: [to_instances]}
        self.protected = set()
        self.model_objs = defaultdict(set)

    def add_edge(self, source, target):
        self.edges.setdefault(source, []).append(target)

    def collect(self, objs, source=None, source_attr=None, **kwargs):
        for obj in objs:
            if source_attr and not source_attr.endswith("+"):
                related_name = source_attr % {
                    "class": source._meta.model_name,
                    "app_label": source._meta.app_label,
                }
                self.add_edge(getattr(obj, related_name), obj)
            else:
                self.add_edge(None, obj)
            self.model_objs[obj._meta.model].add(obj)
        try:
            return super().collect(objs, source_attr=source_attr, **kwargs)
        except models.ProtectedError as e:
            self.protected.update(e.protected_objects)
        except models.RestrictedError as e:
            self.protected.update(e.restricted_objects)

    def related_objects(self, related_model, related_fields, objs):
        qs = super().related_objects(related_model, related_fields, objs)
        return qs.select_related(
            *[related_field.name for related_field in related_fields]
        )

    def _nested(self, obj, seen, format_callback):
        if obj in seen:
            return []
        seen.add(obj)
        children = []
        for child in self.edges.get(obj, ()):
            children.extend(self._nested(child, seen, format_callback))
        if format_callback:
            ret = [format_callback(obj)]
        else:
            ret = [obj]
        if children:
            ret.append(children)
        return ret

    def nested(self, format_callback=None):
        """
        Return the graph as a nested list.
        """
        seen = set()
        roots = []
        for root in self.edges.get(None, ()):
            roots.extend(self._nested(root, seen, format_callback))
        return roots

    def can_fast_delete(self, *args, **kwargs):
        """
        We always want to load the objects into memory so that we can display
        them to the user in confirm page.
        """
        return False

def quote(s):
    """
    Ensure that primary key values do not confuse the admin URLs by escaping
    any '/', '_' and ':' and similarly problematic characters.
    Similar to urllib.parse.quote(), except that the quoting is slightly
    different so that it doesn't get automatically unquoted by the web browser.
    """
    return s.translate(QUOTE_MAP) if isinstance(s, str) else s

def format_json_as_html_list(data):
    """
    Recursively formats JSON data as a nested HTML <ul><li> tree.

    Args:
        data (dict or list): The JSON data to format.

    Returns:
        str: The formatted HTML list tree.
    """
    if isinstance(data, dict):
        result = "<ul>"
        for key, value in data.items():
            result += f"<li>{key}: {format_json_as_html_list(value)}</li>"
        result += "</ul>"
        return result
    elif isinstance(data, list):
        result = "<ul>"
        for item in data:
            result += f"<li>{format_json_as_html_list(item)}</li>"
        result += "</ul>"
        return result
    else:
        return f"{data}"
    
def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    return (
        x_forwarded_for.split(",")[0]
        if x_forwarded_for
        else request.META.get("REMOTE_ADDR")
    )

def get_object_data(instance):
    """Return a dictionary of the object's field values."""
    data = {}
    for field in instance._meta.get_fields():
        value = getattr(instance, field.name, None)

        # Handle concrete fields
        if field.concrete and not isinstance(field, (ForeignKey, OneToOneField, ManyToManyField)):
            if isinstance(value, datetime):
                value = value.strftime("%d-%b-%Y %I:%M:%S %p")  # Format datetime as specified
            elif isinstance(value, ImageFile):
                value = f'<img src="{value.url}" alt="{field.name}">' if value else ''  # Return img tag for image fields
            data[field.name] = value

        # Handle many-to-many relationships
        elif isinstance(field, ManyToManyField):
            if value is not None:
                data[field.name] = [obj.__str__() for obj in value.all()]  # Use the default representation

        # Handle foreign key and one-to-one relationships
        elif isinstance(field, (ForeignKey, OneToOneField)):
            if value is not None:
                data[field.name] = str(value)  # Use the default string representation of the related object

    return data

def url_name_exists(url_name, **kwargs):
    """
    Checks if a URL name exists in the URL patterns.

    This function attempts to resolve the URL pattern associated with the
    given name using the Django reverse URL resolution. If the URL name is
    valid and properly registered in the URL patterns, it returns True. If
    the URL name does not exist or if there is an issue with resolving the
    URL pattern (e.g., missing required parameters), it returns False.

    Parameters:
    - url_name (str): The name of the URL pattern to check.
    - **kwargs: Optional keyword arguments to be passed to the `reverse` function
    if the URL pattern requires parameters. These should match the URL pattern's
    named parameters.

    Returns:
    - bool: True if the URL name exists and can be resolved, False otherwise.

    Example:
    >>> url_name_exists('delete_menu', pk=1)
    True
    >>> url_name_exists('delete_menu')
    False
    """
    try:
        # Attempt to reverse the URL pattern by its name with the provided parameters
        reverse(url_name, kwargs=kwargs)
        return True
    except NoReverseMatch:
        # If the name does not exist or parameters are incorrect, NoReverseMatch is raised
        return False