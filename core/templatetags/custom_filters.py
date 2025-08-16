from django import template
from django.utils.timezone import now
from core.utils.utils import get_filter_choices, get_model
from string import capwords
import datetime
import os

register = template.Library()

@register.filter
def get_key(value, arg):
    """Get the value from a dictionary for the provided key."""
    return value.get(arg, '')

@register.filter
def humanize_field_name(value):
    """
    Converts a field name to human-readable form.

    Handles:
        - Underscores -> spaces
        - Related fields (e.g., profile__department)
        - Django lookup suffixes (e.g., _iexact, _icontains)

    Examples:
        'profile__department_iexact' -> 'Department'
        'profile__department'         -> 'Department'
        'department_iexact'           -> 'Department'
        'department'                  -> 'Department'
        'created_at'                  -> 'Created At'
    """
    if not value:
        return ""

    # Define common Django lookup suffixes
    lookup_suffixes = (
        "_exact", "_iexact", "_contains", "_icontains",
        "_in", "_gt", "_gte", "_lt", "_lte",
        "_startswith", "_istartswith",
        "_endswith", "_iendswith",
        "_range", "_isnull", "_regex", "_iregex"
    )

    # Remove any lookup suffix
    for suffix in lookup_suffixes:
        if value.endswith(suffix):
            value = value[: -len(suffix)]
            break  # only remove one suffix

    # Take the last part after '__' for related fields
    simple_name = value.split("__")[-1]

    # Replace underscores with spaces and capitalize words
    return capwords(simple_name.replace("_", " "))

@register.filter
def get_item(d, key):
    if not isinstance(d, dict):
        return ""
    return d.get(key, "")

@register.inclusion_tag('core/filter_form.html', takes_context=True)
def render_filter_block(context, app_name, model_name, list_filter):
    """Render the filter block dynamically with selected filter values."""
    request = context['request']
    model = get_model(app_name, model_name)
    filter_choices = {field: get_filter_choices(model, field) for field in list_filter}

    # Use filters and search_query from the view context if available
    filters = context.get('filters', {})         # <-- added
    search_query = context.get('search_query', '')  # <-- added

    # Calculate total_count based on the queryset
    queryset = model.objects.all()  # Adjust this if you have specific queryset logic
    total_count = queryset.count()

    # Prepare the reset filters URL
    view_url_name = f'view_{model_name.lower()}'

    return {
        'request': request,
        'filter_choices': filter_choices,
        'list_filter': list_filter,
        'total_count': total_count,
        'view_url_name': view_url_name,
        'filters': filters,               # <-- pass to template
        'search_query': search_query,     # <-- pass to template
    }

@register.filter
def humanize_time(value):
    """Converts a datetime object to a human-readable time format."""
    if not value:
        return ""

    now_time = now()
    time_difference = now_time - value

    if time_difference < datetime.timedelta(minutes=1):
        return "just now"
    elif time_difference < datetime.timedelta(hours=1):
        minutes = int(time_difference.total_seconds() / 60)
        return f"{minutes} mins ago"
    elif time_difference < datetime.timedelta(days=1):
        hours = int(time_difference.total_seconds() / 3600)
        return f"{hours} hours ago"
    elif time_difference < datetime.timedelta(days=2):
        return "yesterday"
    elif time_difference < datetime.timedelta(weeks=1):
        days = time_difference.days
        return f"{days} days ago"
    else:
        # For dates more than a week ago, show the actual date
        return value.strftime("%d %b, %Y")

@register.filter(name='endswith')
def endswith(value, suffix):
    """Custom filter to check if a string ends with a given suffix."""
    if isinstance(value, str):
        return value.lower().endswith(suffix.lower())
    return False

@register.filter(name='truncate_filename')
def truncate_filename(value, length=15):
    """Custom filter to truncate a filename, preserving the extension."""
    if len(value) > length:
        name, ext = os.path.splitext(os.path.basename(value))
        return f"{name[:length-len(ext)-3]}...{ext}"
    return os.path.basename(value)

@register.filter
def as_crispy_field(field):
    return field.as_widget(attrs={'class': 'form-control'})

