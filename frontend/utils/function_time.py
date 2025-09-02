from datetime import datetime, date, time, timedelta

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


