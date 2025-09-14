from datetime import datetime, timedelta, time
from django.utils import timezone
from library.models import Shift
def calculate_minutes_between(date_from, date_to):
    """
    Calculate the time difference between two datetimes in minutes.
    - If date_from and date_to are the same date → return 1440 (24h).
    - If date_to is today → measure from start of date_from to *now*.
    - Accepts datetime/date objects or ISO-like strings.  
    Returns the difference in minutes, or 1440 if parsing fails.
    """
    try:
        # Handle string inputs
        if isinstance(date_from, str):
            date_from = datetime.fromisoformat(date_from.replace('T', ' '))
        if isinstance(date_to, str):
            date_to = datetime.fromisoformat(date_to.replace('T', ' '))

        # Ensure valid types
        if not isinstance(date_from, (datetime, date)) or not isinstance(date_to, (datetime, date)):
            raise ValueError("Inputs must be datetime/date objects or valid ISO strings")

        # Normalize to datetime at midnight if plain date objects
        if isinstance(date_from, date) and not isinstance(date_from, datetime):
            date_from = datetime.combine(date_from, time.min)
        if isinstance(date_to, date) and not isinstance(date_to, datetime):
            date_to = datetime.combine(date_to, time.min)

        today = date.today()

        # Case 1: Same calendar date → fixed 1440 minutes
        if date_from.date() == date_to.date() and date_to.date() != today:
            return 1440

        # Case 2: date_to is today → from start of date_from to now
        if date_to.date() == today:
            date_from = datetime.combine(date_from.date(), time.min)
            date_to = datetime.now()
            return (date_to - date_from).total_seconds() / 60

        # Normal difference
        return (date_to - date_from).total_seconds() / 60

    except Exception:
        return 1440  # default 24h in minutes


def calculate_seconds_between(date_from, date_to):
    """
    Calculate the time difference between two datetimes in minutes.
    - If date_from and date_to are the same date → return 1440 (24h).
    - If date_to is today → measure from start of date_from to *now*.
    - Accepts datetime/date objects or ISO-like strings.  
    Returns the difference in minutes, or 1440 if parsing fails.
    """
    try:
        # Handle string inputs
        if isinstance(date_from, str):
            date_from = datetime.fromisoformat(date_from.replace('T', ' '))
        if isinstance(date_to, str):
            date_to = datetime.fromisoformat(date_to.replace('T', ' '))

        # Ensure valid types
        if not isinstance(date_from, (datetime, date)) or not isinstance(date_to, (datetime, date)):
            raise ValueError("Inputs must be datetime/date objects or valid ISO strings")

        # Normalize to datetime at midnight if plain date objects
        if isinstance(date_from, date) and not isinstance(date_from, datetime):
            date_from = datetime.combine(date_from, time.min)
        if isinstance(date_to, date) and not isinstance(date_to, datetime):
            date_to = datetime.combine(date_to, time.min)

        today = date.today()

        # Case 1: Same calendar date → fixed 1440 minutes
        if date_from.date() == date_to.date() and date_to.date() != today:
            return 1440

        # Case 2: date_to is today → from start of date_from to now
        if date_to.date() == today:
            date_from = datetime.combine(date_from.date(), time.min)
            date_to = datetime.now()
            return (date_to - date_from).total_seconds() 

        # Normal difference
        return (date_to - date_from).total_seconds() 

    except Exception:
        return 86400  # default 24h in seconds


def get_date_range(start_date, end_date):
    """Generate all dates between start and end date"""
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    dates = []
    current = start_date
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    return dates

def format_duration_hms(seconds):
    """
    Format a duration (given in minutes, may include fractions) as Hh Mm Ss.
    """
    if seconds == 0:
        return "0s"

    total_seconds = int(seconds)  # convert to seconds
    hours = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    return f"{hours}h {mins}m {secs}s"


def get_datetime_range(request, default_start_hour=6, default_end_hour=6, show_current_time=True):
    """
    Returns (from_datetime, to_datetime, from_formatted, to_formatted)
    
    Parameters:
        - show_current_time: If True (default), to_datetime is capped at current time.
                      If False, allows to_datetime to be in future (e.g., for reports).
    
    Logic:
    1. Tries to get user-selected datetime_from / datetime_to from GET
    2. Falls back to shift-based times (today's first shift start → last shift end)
    3. If no shifts, falls back to today 6 AM → tomorrow 6 AM
    4. If cap_to_now=True, caps to_datetime at current time
    5. Returns both datetime objects (for DB filtering) and formatted strings (for frontend)
    """
    today = datetime.today().date()
    now = datetime.now()

    # --- Step 1: Get shift-based defaults ---
    first_shift = Shift.objects.first()
    last_shift = Shift.objects.last()

    if first_shift and last_shift:
        from_default = datetime.combine(today, first_shift.start_time)
        to_default = datetime.combine(today, last_shift.end_time)
        if last_shift.end_time <= last_shift.start_time:
            to_default += timedelta(days=1)
    else:
        # Fallback: today 6 AM to tomorrow 6 AM
        from_default = datetime.combine(today, time(default_start_hour, 0))
        to_default = from_default + timedelta(days=1)

    # --- Step 2: Parse user input ---
    datetime_from_str = request.GET.get('datetime_from', '').strip()
    datetime_to_str = request.GET.get('datetime_to', '').strip()

    # Helper to parse frontend datetime string
    def parse_dt(s, fallback):
        if not s:
            return fallback
        for fmt in ['%d/%m/%Y %I:%M %p', '%d/%m/%Y, %I:%M %p']:
            try:
                return datetime.strptime(s, fmt)
            except (ValueError, TypeError):
                continue
        print(f"Failed to parse: '{s}'")
        return fallback

    from_datetime = parse_dt(datetime_from_str, from_default)
    to_datetime = parse_dt(datetime_to_str, to_default)

    # --- Step 3: Conditionally cap end time to now ---
    if show_current_time and to_datetime > now:
        to_datetime = now

    # --- Step 4: Format for frontend (WITH comma for Tempus Dominus)
    from_formatted = from_datetime.strftime('%d/%m/%Y, %I:%M %p')
    to_formatted = to_datetime.strftime('%d/%m/%Y, %I:%M %p')

    return from_datetime, to_datetime, from_formatted, to_formatted