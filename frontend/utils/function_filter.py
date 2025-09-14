from django.db.models import Q
from datetime import datetime, date, time, timedelta
from core.models import ProcessedNPT, RotationStatus, Machine
from library.models import Shift

def is_time_in_shift(time_obj, shift):
    """
    Check if a time falls within a shift, handling overnight shifts.
    
    Args:
        time_obj: time object or datetime object
        shift: Shift object with start_time and end_time
    
    Returns:
        bool: True if time is within shift
    """
    # Handle both time and datetime objects
    if hasattr(time_obj, 'time'):
        check_time = time_obj.time()
    else:
        check_time = time_obj
    
    start_time = shift.start_time
    end_time = shift.end_time
    
    if start_time < end_time:
        # Normal shift (e.g., 08:00 - 16:00)
        return start_time <= check_time < end_time
    else:
        # Overnight shift (e.g., 22:00 - 06:00)
        return check_time >= start_time or check_time < end_time


def filter_by_shift(queryset, shift, datetime_field='off_time'):
    """
    Filter queryset by shift times.
    Handles overnight shifts.
    
    `datetime_field` should be the name of the datetime field on the model
    (e.g., 'count_time' for RotationStatus, 'off_time' for ProcessedNPT).
    """
    start_time = shift.start_time
    end_time = shift.end_time

    if start_time < end_time:
        # Normal shift (e.g., 08:00 - 16:00)
        filter_kwargs = {
            f"{datetime_field}__time__gte": start_time,
            f"{datetime_field}__time__lt": end_time
        }
        return queryset.filter(**filter_kwargs)
    else:
        # Overnight shift (e.g., 22:00 - 06:00)
        return queryset.filter(
            Q(**{f"{datetime_field}__time__gte": start_time}) |
            Q(**{f"{datetime_field}__time__lt": end_time})
        )


def get_shift_for_time(time_obj, shifts):
    """
    Find the shift that contains a given time.
    Handles shifts that cross midnight.
    
    Args:
        time_obj: time object or datetime object
        shifts: iterable of Shift objects
    
    Returns:
        Shift object or None if no matching shift found
    """
    for shift in shifts:
        if is_time_in_shift(time_obj, shift):
            return shift
    return None


def get_current_shift_display(shift_filter):
    """
    Get human-readable shift display
    """
    if shift_filter:
        try:
            shift = Shift.objects.get(id=shift_filter)
            return str(shift)
        except Shift.DoesNotExist:
            pass
    return ''


def get_shift_identifier(shift, all_shifts):
    """
    Get a unique identifier for a shift (name or letter)
    """
    if hasattr(shift, 'name') and shift.name:
        return shift.name.lower()
    else:
        return chr(ord('a') + list(all_shifts).index(shift))
    
def get_shift_duration_seconds(shift):
    """
    Calculate shift duration in seconds, handling overnight shifts
    """
    from datetime import datetime, timedelta
    
    # Create datetime objects for calculation
    start_dt = datetime.combine(datetime.today(), shift.start_time)
    end_dt = datetime.combine(datetime.today(), shift.end_time)
    
    # Handle overnight shifts (end_time < start_time)
    if shift.end_time < shift.start_time:
        end_dt += timedelta(days=1)
    
    duration = end_dt - start_dt
    return duration.total_seconds()





def skip_null_on_time_except_last(npt_qs):
    """
    Skip NPT records with null on_time except for the latest record of each machine.
    """
    # Group by machine
    machines = npt_qs.values_list('machine', flat=True).distinct()
    filtered_qs = ProcessedNPT.objects.none()  # start empty queryset

    for machine_id in machines:
        machine_records = npt_qs.filter(machine_id=machine_id).order_by('off_time')
        if not machine_records.exists():
            continue
        last_record = machine_records.last()  # keep last record even if on_time is null
        # Filter records: exclude null on_time except last
        non_null_records = machine_records.exclude(on_time__isnull=True)
        # Combine with last record (avoid duplication if last_record already non-null)
        if last_record.on_time is None:
            non_null_records = non_null_records | ProcessedNPT.objects.filter(pk=last_record.pk)
        filtered_qs = filtered_qs | non_null_records

    return filtered_qs.distinct()




def parse_filters_and_dates(request=None, **kwargs):
    """
    Parse and validate all filters and dates from request or kwargs
    
    Args:
        request: Django request object (optional)
        **kwargs: Direct parameters (machine, reason, shift, date_from, date_to)
    
    Returns:
        Dict with all parsed filter and date information
    """
    if request:
        print(request.GET)
        if kwargs.get('date_from', ''):
            date_from = kwargs.get('date_from', '')
        else:
            date_from = request.GET.get('date_from', '')
        
        machine_filter = request.GET.get('machine', '')
        reason_filter = request.GET.get('reason', '')
        shift_filter = request.GET.get('shift', '')
        
        date_to = request.GET.get('date_to', '')
    else:
        machine_filter = kwargs.get('machine', '')
        reason_filter = kwargs.get('reason', '')
        shift_filter = kwargs.get('shift', '')
        date_from = kwargs.get('date_from', '')
        date_to = kwargs.get('date_to', '')

    print(reason_filter)
    print(shift_filter)
    print(shift_filter)
    print(date_from)
    print(date_to)
    # Set default date values
    current_date = date.today()
    default_date_from = current_date
    default_date_to = current_date
    
    # Use defaults if not provided
    if not date_from:
        date_from = default_date_from
    if not date_to:
        date_to = default_date_to
    
    # Convert string dates to date objects
    if isinstance(date_from, str):
        try:
            date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
        except ValueError:
            date_from = default_date_from
    
    if isinstance(date_to, str):
        try:
            date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            date_to = default_date_to
    
    # Check if date range is more than one day
    is_multi_day = (date_to - date_from).days > 0
    
    # Generate available days for selection
    available_days = []
    if is_multi_day:
        current_date_iter = date_from
        while current_date_iter <= date_to:
            available_days.append({
                'date': current_date_iter,
                'display': current_date_iter.strftime('%Y-%m-%d (%A)')
            })
            current_date_iter += timedelta(days=1)
    
    return {
        'filters': {
            'machine': machine_filter,
            'reason': reason_filter,
            'shift': shift_filter,
        },
        'dates': {
            'date_from': date_from,
            'date_to': date_to,
            'is_multi_day': is_multi_day,
            'available_days': available_days,
        }
    }


def apply_npt_filters(queryset=None, machine=None, reason=None, shift=None, 
                     date_from=None, date_to=None, single_date=None):
    """
    Apply all NPT filters to a queryset
    
    Args:
        queryset: Base queryset (defaults to all ProcessedNPT records)
        machine: Machine filter value
        reason: Reason filter value  
        shift: Shift filter value
        date_from: Start date for range filtering
        date_to: End date for range filtering
        single_date: Single date for exact date filtering
    
    Returns:
        Filtered queryset
    """
    # Ensure we have a valid queryset
    if queryset is None:
        try:
            queryset = ProcessedNPT.objects.select_related('reason').all()
        except Exception as e:
            # Handle case where model might not be properly imported
            print(f"Error creating base queryset: {e}")
            return ProcessedNPT.objects.none()  # Return empty queryset
    
    # Ensure queryset is not None before applying filters
    if queryset is None:
        return ProcessedNPT.objects.none()
    
    # Apply machine filter
    if machine:
        queryset = queryset.filter(mc_no=machine)
    
    # Apply reason filter
    if reason:
        queryset = queryset.filter(reason__id=reason)
    
    # Apply shift filter
    if shift:
        try:
            shift_obj = Shift.objects.get(id=shift)
            queryset = filter_by_shift(queryset, shift_obj)
        except Shift.DoesNotExist:
            pass
    
    # Apply date filters
    if single_date:
        queryset = queryset.filter(off_time__date=single_date)
    elif date_from and date_to:
        queryset = queryset.filter(off_time__date__gte=date_from, off_time__date__lte=date_to)
    elif date_from:
        queryset = queryset.filter(off_time__date__gte=date_from)
    elif date_to:
        queryset = queryset.filter(off_time__date__lte=date_to)
    
    return queryset