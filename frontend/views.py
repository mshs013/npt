from django.shortcuts import render
from core.middleware import skip_permission
from django.http import JsonResponse, HttpResponse
from datetime import datetime, date, time, timedelta
from django.db.models import Q
from django.utils.timezone import make_aware
from core.models import ProcessedNPT, RotationStatus, Machine, NptReason
from library.models import Shift
import pandas as pd
from core.utils.utils import get_user_machines
from django.contrib.auth.models import AnonymousUser
from itertools import groupby
from operator import itemgetter
from collections import defaultdict
from pprint import pprint
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import math

from core.utils.utils import paginate_queryset
from frontend.utils.function_filter import get_current_shift_display, filter_by_shift,get_shift_for_time,get_shift_identifier,parse_filters_and_dates,apply_npt_filters,skip_null_on_time_except_last,get_shift_duration_seconds
from frontend.utils.function_time import calculate_minutes_between,get_date_range,format_duration_hms,calculate_seconds_between,get_datetime_range
from frontend.utils.function_overall_performance_helper import generate_shift_table,generate_summary_table
from frontend.utils.function_rotation_helper import split_records_by_blocks_multi_day,calculate_npt_minutes


# Create your views here.
@skip_permission
def dashboard(request):
    context = { 'title' : 'Dashboard' }
    return render(request, 'frontend/dashboard.html', context)



### McLogs
@skip_permission
def mclogs(request):
    """
    View to display ProcessedNPT records with filtering capabilities
    """
    # Fetch machines user has access to
    # print(request.user.is_authenticated)
    if request.user is None or isinstance(request.user, AnonymousUser) or not request.user.is_authenticated:
        machines = Machine.objects.none()
        # print(machines)
    else:
        machines = get_user_machines(request.user)
        # print(machines)

    # Get filter parameters from request
    machine_filter = request.GET.get('machine', '')
    reason_filter = request.GET.get('reason', '')
    shift_filter = request.GET.get('shift', '')

    # Set default date values
    date_from, date_to, datetime_from_formatted, datetime_to_formatted = get_datetime_range(request)
    
    duration = date_to - date_from
    time_range_seconds = duration.total_seconds() 

    # Start with all records - use prefetch_related for better performance
    npt_records = ProcessedNPT.objects.select_related('machine', 'reason').filter(machine__in=machines)
    
    # Apply machine filter - Fixed: use machine__id instead of machine__in for single value
    if machine_filter:
        try:
            npt_records = npt_records.filter(machine__id=int(machine_filter))
        except (ValueError, TypeError):
            pass
    
    # Apply reason filter
    if reason_filter:
        try:
            if reason_filter.lower() in ["na", "n/a", "null"]:
                npt_records = npt_records.filter(reason__isnull=True)
            else:
                npt_records = npt_records.filter(reason__id=int(reason_filter))
        except (ValueError, TypeError):
            pass
    
    # Date filtering with better error handling
    if date_from:
        try:
            # from_datetime = datetime.fromisoformat(date_from.replace('T', ' '))
            npt_records = npt_records.filter(off_time__gte=date_from)
        except ValueError:
            pass
    
    if date_to:
        try:
            # to_datetime = datetime.fromisoformat(date_to.replace('T', ' '))
            npt_records = npt_records.filter(off_time__lte=date_to)
        except ValueError:
            pass
    
    # Shift filtering
    if shift_filter:
        try:
            shift = Shift.objects.get(id=int(shift_filter))
            time_range_seconds = get_shift_duration_seconds(shift)
            npt_records = filter_by_shift(npt_records, shift)
        except (Shift.DoesNotExist, ValueError, TypeError):
            pass
    
    # Order by most recent first
    npt_records = skip_null_on_time_except_last(npt_records)
    npt_qs = npt_records.order_by('-off_time')

    

    npt_qs, paginator = paginate_queryset(request, npt_qs, 50)

    # Calculate time range in seconds
    # time_range_seconds = calculate_seconds_between(date_from, date_to)
    
    # Process data in single loop for efficiency
    reason_counts = {}
    machine_data = {}

    
    for record in npt_records:
        reason_name = record.reason.name if record.reason else 'N/A'
        machine_name = record.machine.mc_no
        duration = record.get_duration().total_seconds()
        
        # Count reasons
        reason_counts[reason_name] = reason_counts.get(reason_name, 0) + 1
        
        # Accumulate machine data
        if machine_name not in machine_data:
            machine_data[machine_name] = {}
        machine_data[machine_name][reason_name] = machine_data[machine_name].get(reason_name, 0) + duration
        

    # Format reasons data
    reasons = [
        {"name": reason_name, "count": count}
        for reason_name, count in reason_counts.items()
    ]
    
    # Format shifts data
    all_shifts = Shift.objects.all().order_by('start_time')
    shifts = [
        {"name": str(shift), "time": f"{shift.start_time} - {shift.end_time}"}
        for shift in all_shifts
    ]
    
    # Format machines data with NPT percentages
    machines_list = []
    total_npt_all = 0
    
    for machine_name, reason_durations in machine_data.items():
        machine_reasons = [
            {"name": reason_name, "duration": format_duration_hms(duration)}
            for reason_name, duration in reason_durations.items()
        ]
        total_machine_npt = sum(reason_durations.values())
        total_npt_all += total_machine_npt

        # Calculate NPT percentage
        npt_percentage = round((total_machine_npt / time_range_seconds) * 100, 2) if time_range_seconds > 0 else 0
        # print("Machine: ", machine_name, " NPT: ", total_machine_npt, " Duration: ", time_range_seconds)
        machines_list.append({
            "name": machine_name,
            "reasons": machine_reasons,
            "total_npt": format_duration_hms(round(total_machine_npt, 2)),
            "npt_percentage": npt_percentage,
        })

    ###     Total NPT Percentage Formula    ###
    #   total_npt_all -> sum of npts of all machines
    #   total_machines_no -> no of machines that produced npt during the datetime range
    #   time_range_seconds -> the duration in seconds between datetime range or shift duration (usually 8 hours)
    #   time_range_seconds*total_machines_no -> to get total duration across all machines otherwise the npt % would be way over 100%
    #   Equation -> total_npt_percentage = total_npt_all/(time_range_seconds*total_machines_no)
    

    machine_choices = machines.filter(is_deleted=False)  # Assuming SoftDeleteModel has is_deleted
    all_reasons = NptReason.objects.filter(is_deleted=False).order_by('name')
    total_machines_no = len(machines_list) if len(machines_list) != 0 else 1
    total_npt_percentage = total_npt_all/(time_range_seconds*total_machines_no)
    # Calculate totals
    total_reason_counts = sum(reason['count'] for reason in reasons)
    context = {
        'reasons': reasons,
        'shifts': shifts,
        'machines': machines_list,
        'page_obj': npt_qs,
        'total_npt_all': format_duration_hms(round(total_npt_all, 2)),
        'total_npt_percentage': round(total_npt_percentage*100, 2),
        'total_reason_counts': total_reason_counts,
        'time_range_minutes': time_range_seconds,
        # Filter options
        'filter_machines': machine_choices,
        'filter_reasons': all_reasons,
        'filter_shifts': all_shifts,
        'datetime_from': datetime_from_formatted,
        'datetime_to': datetime_to_formatted,
        'current_shift': get_current_shift_display(shift_filter),
        'footer_colspan': 2 + len(reasons),
        'title':'Machine Logs',
    }
    
    return render(request, 'frontend/mclogs.html', context)


@skip_permission
def mcgraph(request):
    """Render the NPT chart page"""
    context = { 'title' : 'Machine Graph' }
    return render(request, 'frontend/mcgraph.html', context)


def mcgraph_api(request):
    """API endpoint to provide NPT data for the chart"""
    try:
        current_date = date.today()
        start_of_day = datetime.combine(current_date, time.min)
        end_of_day = datetime.combine(current_date, time.max)

        # Fixed the query to match the actual model structure
        rows = (ProcessedNPT.objects
              .filter(off_time__gte=start_of_day, off_time__lte=end_of_day)
              .select_related('reason')
              .order_by('mc_no', 'off_time')
              .values('mc_no', 'reason__name', 'off_time', 'on_time'))

        # removing null values
        rows = skip_null_on_time_except_last(rows)

        npt = [{
            'machine_name': row['mc_no'],  # Just using mc_no since we don't have machine relationship
            'reason_name': row['reason__name'] if row['reason__name'] else 'N/A',
            'off_time': row['off_time'].isoformat(),
            'on_time': row['on_time'].isoformat() if row['on_time'] else None,
        } for row in rows]

        print(npt)
        return JsonResponse({
            'success': True,
            'npt': npt,
            'date': current_date.isoformat(),
            'total': len(npt),
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    

### Rotation Counter
@skip_permission
def rotaionCounter(request):
    # Fetch machines user has access to
    if request.user is None or isinstance(request.user, AnonymousUser) or not request.user.is_authenticated:
        machines = Machine.objects.none()
    else:
        machines = get_user_machines(request.user)

    # print(machines)
    
    # Get filter parameters from request
    machine_filter = request.GET.get('machine', '29')
    shift_filter = request.GET.get('shift', '')
    
    from_datetime, to_datetime, datetime_from_formatted, datetime_to_formatted = get_datetime_range(request)
    
    #pprint(datetime_from_formatted)
    #pprint(datetime_to_formatted)

    #print(from_datetime)
    #print(to_datetime)


    duration = to_datetime - from_datetime
    total_duration_minutes = duration.total_seconds() / 60

    # Base queryset for rotation records - filter by user machines
    rotation_qs = RotationStatus.objects.select_related('machine').filter(
        machine__in=machines,
        #count_time__range=(from_datetime, to_datetime),
        # count_time__lte=to_datetime
    ).filter(
        Q(count_time__lte=to_datetime) & Q(count_time__gte=from_datetime)
    )
    
    # Base queryset for NPT records - filter by user machines
    npt_qs = ProcessedNPT.objects.select_related('machine', 'reason').filter(
        machine__in=machines
    ).filter(
        Q(off_time__lte=to_datetime) & (Q(on_time__gte=from_datetime) | Q(on_time__isnull=True))
    )

    # Apply machine filter
    if machine_filter:
        try:
            rotation_qs = rotation_qs.filter(machine__mc_no=machine_filter)
            npt_qs = npt_qs.filter(machine__mc_no=machine_filter)
        except (ValueError, TypeError):
            pass

    # Apply shift filter
    shifts = Shift.objects.all().order_by('start_time')
    current_shift_display = ''
    
    if shift_filter:
        try:
            selected_shift = Shift.objects.get(id=int(shift_filter))
            current_shift_display = str(selected_shift)
            # print("Shift Selected: ", selected_shift)
            total_duration_minutes = get_shift_duration_seconds(selected_shift)/60
            # Filter by shift time using the utility function
            rotation_qs = filter_by_shift(rotation_qs, selected_shift, "count_time")
            npt_qs = filter_by_shift(npt_qs, selected_shift)
            
        except (Shift.DoesNotExist, ValueError, TypeError):
            pass
    
    # Skipping Null on_Times from npt_qs
    npt_qs = skip_null_on_time_except_last(npt_qs)

    # Build Q object for all NPT intervals
    exclude_q = Q()
    for npt in npt_qs:
        start = npt.off_time
        end = npt.on_time or to_datetime  # Ongoing NPT
        if start.tzinfo is None:
            start = make_aware(start)
        if end.tzinfo is None:
            end = make_aware(end)
        exclude_q |= Q(count_time__gte=start, count_time__lt=end)

    # Exclude rotations during NPT
    rotation_qs = rotation_qs.exclude(exclude_q)

    # Fetch records ordered for processing rolls (chronologically per machine)
    page_obj = rotation_qs.order_by('machine__mc_no', '-count_time')

    rotation_records, paginator = paginate_queryset(request, page_obj, 50)
    #print(rotation_qs.query)
    #print(len(rotation_records))
    # print(len(page_obj))
    # exit()

    # Calculate total duration of the selected window
    # duration = to_datetime - from_datetime
    # total_duration_minutes = duration.total_seconds() / 60
    
    
   # --- Roll Processing Logic (Improved) ---
    all_rolls = []
    # Group records by machine object to process each machine's rolls separately
    for machine, machine_records_iter in groupby(rotation_qs, key=lambda r: r.machine):
        if not machine:  # Skip records with no machine
            continue
            
        machine_records = list(machine_records_iter)
        mc_no = machine.mc_no
        
        current_roll_records = []
        roll_no_counter = 1
        previous_count = None
        
        for record in machine_records:
            # A new roll starts when count decreases from the previous count
            # or when we have no previous count (first record)
            
            if previous_count is not None and record.count < previous_count and current_roll_records:
                # Process the completed roll before starting the new one
                start_record = current_roll_records[0]
                end_record = current_roll_records[-1]
                
                start_time = start_record.count_time
                end_time = end_record.count_time
                # Calculate actual rotations during this roll period
                
                total_count = end_record.count - start_record.count + 1
                duration = end_time - start_time
                duration_minutes = duration.total_seconds() / 60 if duration.total_seconds() > 0 else 0
                
                # Calculate NPT in minutes for the roll
                roll_npt = npt_qs.filter(
                    machine=machine,
                    off_time__gte=start_time,
                    off_time__lt=end_time
                )
                npt_minutes = sum(npt.get_duration().total_seconds() / 60 for npt in roll_npt)
                # print("npt Min: ", npt_minutes)
                # Productive duration
                productive_minutes = duration_minutes - npt_minutes
                # print(productive_minutes)
                if productive_minutes < 0:
                    productive_minutes = 0  # avoid negative time

                # Calculate avg_rpm using productive time
                avg_rpm = 0
                if productive_minutes > 0 and total_count > 0:
                    revolutions = total_count 
                    avg_rpm = revolutions / productive_minutes

                all_rolls.append({
                    'mc_no': mc_no,
                    'roll_no': f"Roll-{roll_no_counter}",
                    'start_time': start_time,
                    'end_time': end_time,
                    'total_count': total_count,
                    'duration_minutes': duration_minutes,
                    'productive_minutes': productive_minutes,
                    'npt_minutes': round(npt_minutes, 2),
                    'avg_rpm': round(avg_rpm, 2)
                })
                roll_no_counter += 1

                # Start new roll with the current record
                current_roll_records = [record]
            else:
                # Continue adding to current roll
                current_roll_records.append(record)
            
            # Update previous count for next iteration
            previous_count = record.count
        
        
        # After the loop, process the last remaining roll for the machine
        if current_roll_records:
            start_record = current_roll_records[0]
            end_record = current_roll_records[-1]
            
            start_time = start_record.count_time
            end_time = end_record.count_time
            total_count = end_record.count - start_record.count + 1

            duration = end_time - start_time
            duration_minutes = duration.total_seconds() / 60 if duration.total_seconds() > 0 else 0

            # Calculate NPT in minutes for the roll
            roll_npt = npt_qs.filter(
                machine=machine,
                off_time__gte=start_time,
                off_time__lt=end_time
            )
            npt_minutes = 0
            for npt in roll_npt:
                if hasattr(npt, 'get_duration') and callable(npt.get_duration):
                    # Use the model's get_duration method if available
                    npt_minutes += npt.get_duration().total_seconds() / 60
                else:
                    # Manual calculation: handle null on_time
                    if npt.on_time:
                        duration = npt.on_time - npt.off_time
                        npt_minutes += duration.total_seconds() / 60
                    else:
                        # For ongoing NPT (null on_time), calculate till roll end
                        duration = end_time - npt.off_time
                        npt_minutes += duration.total_seconds() / 60

            # Productive duration
            productive_minutes = duration_minutes - npt_minutes
            if productive_minutes < 0:
                productive_minutes = 0  # avoid negative time

            # Calculate avg_rpm using productive time
            avg_rpm = 0
            if productive_minutes > 0 and total_count > 1:
                revolutions = total_count 
                avg_rpm = revolutions / productive_minutes
            
            all_rolls.append({
                'mc_no': mc_no,
                'roll_no': f"Roll-{roll_no_counter}",
                'start_time': start_time,
                'end_time': end_time,
                'total_count': total_count,
                'duration_minutes': duration_minutes,
                'productive_minutes': productive_minutes,
                'npt_minutes': round(npt_minutes, 2),
                'avg_rpm': round(avg_rpm, 2)
            })


    # print(all_rolls)
    # 1. Intermediary Roll Data (sorted by start time, descending)
    intermediary_data = sorted(all_rolls, key=itemgetter('start_time'), reverse=True)
    for i, roll in enumerate(intermediary_data, 1):
        roll['serial_no'] = i

    # 2. Machine Wise Summary with Total Counts
    machine_wise_summary = []
    machine_data = defaultdict(list)
    for roll in all_rolls:
        machine_data[roll['mc_no']].append(roll)

    for mc_no, rolls in machine_data.items():
        total_rolls = len(rolls)
        total_counts = sum(r['total_count'] for r in rolls)
        total_duration = sum(r['duration_minutes'] for r in rolls)
        total_productive = sum(r['productive_minutes'] for r in rolls)
        total_npt = sum(r['npt_minutes'] for r in rolls) + (total_duration_minutes-total_duration)
        #print("Total Npt: ", total_npt)
        #print("total_counts: ", total_counts)
        #print("total_duration_minutes: ", total_duration_minutes)
        #print("total_duration: ",total_duration)
        # Calculate overall average RPM based on total counts and total productive time
        overall_avg_rpm = 0
        if total_productive > 0 and total_counts > 0:
            overall_avg_rpm = total_counts / total_productive
        
        machine_wise_summary.append({
            'mc_no': mc_no,
            'total_counts': total_counts,
            'avg_rpm': round(overall_avg_rpm, 2),
            'total_productive': total_productive,
            'npt_minutes': round(total_npt, 2),
            'total_duration':round(total_duration_minutes,2),
            'total_rolls': total_rolls
        })

    machine_wise_summary.sort(key=itemgetter('mc_no'))

    # 3. Rotation Counter Log (Raw Data, descending by time)
    rotation_log_records = rotation_qs.order_by('-count_time')
    rotation_log = []
    for i, record in enumerate(rotation_log_records, 1):
        rotation_log.append({
            'serial_no': i,
            'mc_no': record.machine.mc_no if record.machine else 'N/A',
            'count_time': record.count_time,
            'count_no': record.count
        })
    # sorting raw rotation data by count time in decending order
    rotation_log.sort(key=lambda x: x["count_time"], reverse=True)

    # Get filter options for the dropdown - only machines user has access to
    if hasattr(machines, 'filter'):
        # machines is a QuerySet
        machine_choices = machines.filter(is_deleted=False).values_list('mc_no', flat=True).distinct().order_by('mc_no')
    else:
        # machines is a list/other iterable
        machine_choices = Machine.objects.filter(id__in=machines, is_deleted=False).values_list('mc_no', flat=True).distinct().order_by('mc_no')
    
    # Calculate totals for footer
    total_rolls_summary = sum(data['total_rolls'] for data in machine_wise_summary)
    total_counts_summary = sum(data['total_counts'] for data in machine_wise_summary)
    total_npt_summary = sum(data['npt_minutes'] for data in machine_wise_summary)
    overall_avg_rpm = 0
    total_productive_all = 0

    if machine_wise_summary:
        total_productive_all = sum(roll['productive_minutes'] for roll in all_rolls)
        if total_productive_all > 0 and total_counts_summary > 0:
            overall_avg_rpm = total_counts_summary / total_productive_all

    # print("Total Duration: ", total_duration_minutes)
    # print("Machine Running Time: ", round(total_productive_all+total_npt_summary,2))
    # print("NPT: ", total_npt_summary)
    context = {
        'machine_wise_summary': machine_wise_summary,
        'intermediary_data': intermediary_data,
        'page_obj': rotation_records,
        'filter_machines': machine_choices,
        'filter_shifts': shifts,
        'selected_machine': machine_filter,
        'selected_shift': shift_filter,
        'current_shift_display': current_shift_display,
        'datetime_from': datetime_from_formatted,
        'datetime_to': datetime_to_formatted,
        'total_rolls': total_rolls_summary,
        'total_counts': total_counts_summary,
        'total_npt': total_npt_summary,
        'total_productive_all':round(total_productive_all+total_npt_summary,2),
        'overall_avg_rpm': round(overall_avg_rpm, 2),
        'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'superuser': request.user.is_superuser,
        'title': 'Rotation Counter',
    }
    
    return render(request, 'frontend/rotation_counter.html', context)


### Report - daily performance
@skip_permission
def daily_performance(request, user=None):
    """
    View to display ProcessedNPT records with filtering capabilities
    """
    # Fetch machines user has access to
    if request.user is None or isinstance(request.user, AnonymousUser) or not request.user.is_authenticated:
        machines = Machine.objects.none()
    else:
        machines = get_user_machines(request.user)

    # Get filter parameters from request
    machine_filter = request.GET.get('machine', '')
    reason_filter = request.GET.get('reason', '')
    shift_filter = request.GET.get('shift', '')

    date_from, date_to, datetime_from_formatted, datetime_to_formatted = get_datetime_range(request, show_current_time=False)
    
    # Start with all records - filter by user machines
    npt_records = ProcessedNPT.objects.select_related('machine', 'reason').filter(machine__in=machines)
    
    # Apply machine filter
    if machine_filter:
        try:
            npt_records = npt_records.filter(machine__id=int(machine_filter))
        except (ValueError, TypeError):
            pass
    
    # Apply reason filter
    if reason_filter:
        try:
            npt_records = npt_records.filter(reason__id=int(reason_filter))
        except (ValueError, TypeError):
            pass
    
    if date_from:
        try:
            # from_datetime = datetime.fromisoformat(date_from.replace('T', ' '))
            npt_records = npt_records.filter(off_time__gte=date_from)
        except ValueError:
            pass
    
    if date_to:
        try:
            # to_datetime = datetime.fromisoformat(date_to.replace('T', ' '))
            npt_records = npt_records.filter(off_time__lte=date_to)
        except ValueError:
            pass
    
    # Shift filtering using dynamic shifts
    if shift_filter:
        try:
            shift = Shift.objects.get(id=int(shift_filter))
            npt_records = filter_by_shift(npt_records, shift)
        except (Shift.DoesNotExist, ValueError, TypeError):
            pass
    
    # Order by most recent first
    npt_records = npt_records.order_by('-off_time')
    npt_records = skip_null_on_time_except_last(npt_records)
    # Calculate time range in minutes
    time_range_minutes = calculate_seconds_between(date_from, date_to)

    # Process data in single loop for efficiency
    reason_counts = {}
    reason_durations = {}  # For total NPT time per reason
    machine_data = {}
    npt_data = []
    
    for record in npt_records:
        reason_name = record.reason.name if record.reason else 'N/A'
        machine_name = record.machine.mc_no
        duration_minutes = record.get_duration().total_seconds()/60
        duration_timedelta = record.get_duration().total_seconds()
        
        # Count reasons and accumulate durations
        reason_counts[reason_name] = reason_counts.get(reason_name, 0) + 1
        reason_durations[reason_name] = reason_durations.get(reason_name, 0) + duration_timedelta
        
        # Accumulate machine data
        if machine_name not in machine_data:
            machine_data[machine_name] = {
                "reasons": {},  # Store reason durations
                "count": 0      # Initialize count
            }
        
        # Add duration for the reason
        machine_data[machine_name]["reasons"][reason_name] = machine_data[machine_name]["reasons"].get(reason_name, 0) + duration_minutes
        
        # Increment total count for this machine
        machine_data[machine_name]["count"] += 1
        
        # Collect NPT data
        npt_data.append({
            "machine": machine_name,
            "reason": reason_name,
            "offTime": record.off_time,
            "onTime": record.on_time,
            "duration": duration_minutes
        })
    
    # Format reasons data
    reasons = [
        {"name": reason_name, "count": count, "total_duration": reason_durations.get(reason_name, 0)}
        for reason_name, count in reason_counts.items()
    ]
    
    # Format shifts data
    all_shifts = Shift.objects.all().order_by('start_time')
    shifts = [
        {"name": str(shift), "time": f"{shift.start_time} - {shift.end_time}"}
        for shift in all_shifts
    ]
    
    # Format machines data
    machines_list = []
    total_npt_all = 0
    
    for machine_name, data in machine_data.items():
        reason_durations_dict = data["reasons"]
        events = data["count"]
        machine_reasons = [
            {"name": reason_name, "duration": round(duration, 2)}
            for reason_name, duration in reason_durations_dict.items()
        ]
        machine_reasons.sort(key=lambda x: x["duration"], reverse=True)
        total_machine_npt = sum(reason_durations_dict.values())
        total_npt_all += total_machine_npt
        
        # Calculate NPT percentage
        npt_percentage = round((total_machine_npt / time_range_minutes) * 100, 2) if time_range_minutes > 0 else 0
        
        machines_list.append({
            "name": machine_name,
            "most_npt_reason": machine_reasons[0] if machine_reasons else {"name": "N/A", "duration": 0},
            "total_events": events,
            "total_npt": round(total_machine_npt, 2),
            "avg_npt_per_event": round(total_machine_npt/events, 1) if events else 0,
            "reasons": reason_durations_dict,
            "npt_percentage": npt_percentage
        })
    
    # Sort machines by name
    machines_list.sort(key=lambda x: x["name"], reverse=False)
    
    # Calculate totals
    total_reason_counts = sum(reason['count'] for reason in reasons)
    total_avg_npt_per_events = round(total_npt_all / total_reason_counts, 2) if total_reason_counts else 0

    # Get dropdown options for filters - only machines user has access to
    if hasattr(machines, 'filter'):
        # machines is a QuerySet
        machine_choices = machines.filter(is_deleted=False).values_list('mc_no', flat=True).distinct().order_by('mc_no')
    else:
        # machines is a list/other iterable
        machine_choices = Machine.objects.filter(id__in=machines, is_deleted=False).values_list('mc_no', flat=True).distinct().order_by('mc_no')
    
    all_reasons = NptReason.objects.filter(is_deleted=False).order_by('name')

    # ========== PLOTLY CHARTS ==========
    
    # 1. BAR CHART - Machine-wise NPT
    if machines_list:
        machine_names = [machine['name'] for machine in machines_list]
        machine_npt_values = [machine['total_npt'] for machine in machines_list]
        
        bar_chart = go.Figure(data=[
            go.Bar(
                x=machine_names,
                y=machine_npt_values,
                text=[f"{val:.1f} min" for val in machine_npt_values],
                textposition='auto',
                marker_color='rgba(55, 128, 191, 0.7)',
                marker_line_color='rgba(55, 128, 191, 1.0)',
                marker_line_width=2
            )
        ])
        
        bar_chart.update_layout(
            title={
                'text': 'Machine-wise NPT (Non-Productive Time)',
                'x': 0.5,
                'xanchor': 'center'
            },
            # xaxis_title='Machine Number',
            yaxis_title='NPT (Minutes)',
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(size=12),
            height=350,
            bargap=0.4  # Make bars thinner by increasing gap
        )
        
        bar_chart_html = bar_chart.to_html(
            include_plotlyjs='cdn', 
            div_id="bar-chart",
            config={
                'displayModeBar': True, 
                'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d', 'autoScale2d', 'zoomIn2d', 'zoomOut2d'],
                'responsive': True
            }
        )
    else:
        bar_chart_html = '<div style="text-align: center; padding: 50px; color: #666;">No data available for bar chart</div>'

    # 2. PIE CHART - Reason-wise NPT (All Machines Combined)
    if reason_durations:
        # Calculate total NPT and percentages for each reason
        total_npt_time = sum(reason_durations.values())
        reason_names = list(reason_durations.keys())
        reason_values = list(reason_durations.values())
        reason_percentages = [(val/total_npt_time)*100 for val in reason_values]
        
        # Create custom labels with NPT time and percentage for legend
        legend_labels = [
            f"{name} ({val:.1f} min, {pct:.1f}%)"
            for name, val, pct in zip(reason_names, reason_values, reason_percentages)
        ]
        
        pie_chart = go.Figure(data=[
            go.Pie(
                labels=legend_labels,  # Use custom labels with time and percentage for legend
                values=reason_values,
                text=reason_names,  # Simple reason names for arc labels
                textinfo='text+percent',  # Show only text and percent on arcs
                textposition='inside',
                textfont=dict(color="#F7F7F7", size=11),  # White text for all arc labels
                hovertemplate='<b>%{label}</b><br>NPT: %{value:.1f} min<br>Percentage: %{percent}<extra></extra>',
                marker=dict(line=dict(color='#000000', width=1))
            )
        ])
        
        pie_chart.update_layout(
            title={
                'text': 'NPT Distribution by Reason (All Machines)',
                'x': 0.5,
                'xanchor': 'center'
            },
            font=dict(size=11),
            height=400,
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.02,
                font=dict(size=10)
            )
        )
        
        pie_chart_html = pie_chart.to_html(
            include_plotlyjs=False, 
            div_id="pie-chart",
            config={
                'displayModeBar': True, 
                'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d', 'autoScale2d', 'resetScale2d', 'zoomIn2d', 'zoomOut2d'],
                'responsive': True
            }
        )
    else:
        pie_chart_html = '<div style="text-align: center; padding: 50px; color: #666;">No data available for pie chart</div>'

    # 3. DONUT CHARTS - Multiple machines in a subplot grid (5 per row)
    if machines_list and any(machine['reasons'] for machine in machines_list):
        # Calculate grid dimensions (5 columns, as many rows as needed)
        machines_with_data = [m for m in machines_list if m['reasons']]
        total_machines = len(machines_with_data)
        cols = 5
        rows = math.ceil(total_machines / cols)

        # Create specs for subplots - all domain type for pie charts
        specs = [[{'type': 'domain'} for _ in range(cols)] for _ in range(rows)]

        # Create subplots
        donut_subplots = make_subplots(
            rows=rows, 
            cols=cols, 
            specs=specs,
            subplot_titles=[f"{machine['name']}" for machine in machines_with_data],
            horizontal_spacing=0.05,
            vertical_spacing=0.1
        )

        # Add each machine's donut chart to the subplot
        for idx, machine in enumerate(machines_with_data):
            row = (idx // cols) + 1
            col = (idx % cols) + 1

            machine_reason_names = list(machine['reasons'].keys())
            machine_reason_values = list(machine['reasons'].values())
            machine_total_npt = sum(machine_reason_values)
            
            # Calculate percentages for each reason
            machine_reason_percentages = [(val/machine_total_npt)*100 for val in machine_reason_values]
            
            # Create custom text with format "reason (npt, xx%)"
            custom_text = [
                f"{name}<br>({val:.1f}min, {pct:.1f}%)"
                for name, val, pct in zip(machine_reason_names, machine_reason_values, machine_reason_percentages)
            ]

            donut_subplots.add_trace(
                go.Pie(
                    labels=machine_reason_names,
                    values=machine_reason_values,
                    text=custom_text,  # Custom formatted text
                    hole=0.3,  # Donut effect
                    name=f"{machine['name']}",
                    textinfo='text',  # Show only the custom text
                    textfont=dict(color="#2E2D2D", size=8),
                    textposition='auto',
                    hovertemplate='<b>%{label}</b><br>NPT: %{value:.1f} min<br>Percentage: %{percent}<extra></extra>',
                    marker=dict(line=dict(color='#000000', width=1)),
                    showlegend=True
                ),
                row=row, col=col
            )

        # Update layout for the subplot
        donut_subplots.update_layout(
            title={
                'text': 'Machine-wise NPT Breakdown by Reason',
                'x': 0.5,
                'y': 0.95,
                'xanchor': 'center',
                'font': {'size': 16}
            },
            font=dict(size=10),
            height=425 * rows,  # Adjust height based on number of rows
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.2,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            )
        )

        # Update subplot titles
        donut_subplots.update_annotations(font_size=12)

        donut_charts_html = donut_subplots.to_html(
            include_plotlyjs=False,
            div_id="donut-charts-grid",
            config={'displayModeBar': True,
                    'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d', 'autoScale2d', 'resetScale2d', 'zoomIn2d', 'zoomOut2d'],
                    'responsive': True}
        )
    else:
        donut_charts_html = '<div style="text-align: center; padding: 50px; color: #666;">No machine data available for donut charts</div>'
        
    context = {
        'reasons': reasons,
        'shifts': shifts,
        'machines': machines_list,
        'npt_data': npt_data,
        'total_npt_all': round(total_npt_all, 2),
        'total_reason_counts': total_reason_counts,
        'total_avg_npt_per_events': total_avg_npt_per_events,
        'time_range_minutes': time_range_minutes,
        # Original filter options
        'filter_machines': machine_choices,
        'filter_reasons': all_reasons,
        'filter_shifts': all_shifts,
        'datetime_from': datetime_from_formatted,
        'datetime_to': datetime_to_formatted,
        'current_shift': get_current_shift_display(shift_filter),
        'footer_colspan': 2,
        # Plotly charts as HTML
        'bar_chart_html': bar_chart_html,
        'pie_chart_html': pie_chart_html,
        'donut_charts_html': donut_charts_html,
        'title' : 'Daily Performance',
    }
    
    return render(request, 'frontend/daily_performance.html', context)### Overall Performance

@skip_permission
def overall_performance(request, user=None):
    """
    View to display ProcessedNPT records with filtering capabilities
    """
    # Fetch machines user has access to
    if request.user is None or isinstance(request.user, AnonymousUser) or not request.user.is_authenticated:
        machines = Machine.objects.none()
    else:
        machines = get_user_machines(request.user)


    # Parse all filters and dates with custom defaults for this view
    current_date = date.today()
    default_date_from = current_date - timedelta(days=6)  # 7 days including today
    
    parsed_data = parse_filters_and_dates(
        request, 
        date_from=request.GET.get('date_from', default_date_from.strftime("%Y-%m-%d")),
    )

    # Start with records filtered by user machines
    npt_records = ProcessedNPT.objects.select_related('machine', 'reason').filter(machine__in=machines)

    filters = parsed_data['filters']
    dates = parsed_data['dates']
    
    # Apply all filters at once
    npt_records = apply_npt_filters(
        queryset=npt_records,
        machine=filters['machine'],
        reason=filters['reason'],
        shift=filters['shift'],
        date_from=dates['date_from'],
        date_to=dates['date_to']
    )

    all_shifts = Shift.objects.all().order_by('start_time')
    
    # Get machines to display from filtered records
    machines_to_display = npt_records.values_list('machine__mc_no', flat=True).distinct().order_by('machine__mc_no')
    
    date_range = get_date_range(dates['date_from'], dates['date_to'])
    date_headers = [{'date': d, 'display': d.strftime('%d %a'), 'full_display': d.strftime('%d %b, %Y')} for d in date_range]

    machine_date_data = defaultdict(lambda: defaultdict(lambda: {
        'total_npt': 0, 'shifts': defaultdict(lambda: {'npt': 0})
    }))

    chart_data = [] # For Plotly charts
    # removing null values
    npt_records = skip_null_on_time_except_last(npt_records)

    for record in npt_records:
        machine = record.machine.mc_no
        record_date = record.off_time.date()
        duration_min = record.get_duration().total_seconds()/60
        
        shift_obj = get_shift_for_time(record.off_time, all_shifts)
        shift_id = get_shift_identifier(shift_obj, all_shifts) if shift_obj else 'N/A'
        
        machine_date_data[machine][record_date]['total_npt'] += duration_min
        machine_date_data[machine][record_date]['shifts'][shift_id]['npt'] += duration_min
        
        # Append data for charts
        chart_data.append({
            "Date": record_date,
            "Machine": machine,
            "NPT": duration_min 
        })

    # Overall NPT Summary Table
    table1_data = generate_summary_table(machines_to_display, date_range, date_headers, machine_date_data)

    # Shift-wise Tables
    shifts_for_tables = Shift.objects.filter(id=filters['shift']) if filters['shift'] else all_shifts
    shift_tables = {}
    for shift in shifts_for_tables:
        shift_id = get_shift_identifier(shift, all_shifts)
        shift_tables[shift_id] = generate_shift_table(
            shift, shift_id, machines_to_display, date_range, date_headers, machine_date_data
        )

    bar_chart_html = None
    line_chart_html = None
    plotly_config = {
                'displayModeBar': True, 
                'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d', 'autoScale2d', 'zoomIn2d', 'zoomOut2d'],
                'responsive': True
            }

    if chart_data:
        df = pd.DataFrame(chart_data)
        daily_npt = df.groupby(['Date', 'Machine'])['NPT'].sum().reset_index()

        fig_bar = px.bar(
            daily_npt,
            x='Date',
            y='NPT',
            color='Machine',
            title='Daily NPT by Machine (Stacked)',
            labels={'NPT': 'NPT (Min)', 'Date': 'Date'},
            height=400
        )
        fig_bar.update_layout(
            barmode='stack',
            plot_bgcolor='white',
            paper_bgcolor='white'
        )

        # --- Area Chart (smoothed) ---
        fig_area = px.area(
            daily_npt,
            x='Date',
            y='NPT',
            color='Machine',
            title='Daily NPT by Machine (Trend)',
            labels={'NPT': 'NPT (Min)', 'Date': 'Date'},
            height=400
        )
        fig_area.update_traces(
            line_shape='spline',  # smooth curves
            opacity=0.3            # light area fill
        )
        fig_area.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white'
        )

        # --- Plotly config for modebar and zoom ---
        plotly_config = {
            'displayModeBar': True,
            'displaylogo': False,
            'scrollZoom': True
        }

        bar_chart_html = fig_bar.to_html(full_html=False, include_plotlyjs='cdn', config=plotly_config)
        line_chart_html = fig_area.to_html(full_html=False, include_plotlyjs='cdn', config=plotly_config)

    # Get dropdown options for filters - only machines user has access to
    if hasattr(machines, 'filter'):
        # machines is a QuerySet
        machine_choices = machines.filter(is_deleted=False).values_list('mc_no', flat=True).distinct().order_by('mc_no')
    else:
        # machines is a list/other iterable
        machine_choices = Machine.objects.filter(id__in=machines, is_deleted=False).values_list('mc_no', flat=True).distinct().order_by('mc_no')

    context = {
        "date_from": dates['date_from'],
        "date_to": dates['date_to'],
        "table1_data": table1_data,
        "shift_tables": shift_tables,
        'filter_machines': machine_choices,
        'filter_reasons': NptReason.objects.filter(is_deleted=False).order_by('name'),
        'filter_shifts': all_shifts,
        'current_machine': filters['machine'],
        'current_reason': int(filters['reason']) if filters['reason'] else None,
        'current_shift_id': int(filters['shift']) if filters['shift'] else None,
        'bar_chart_html': bar_chart_html,
        'line_chart_html': line_chart_html,
        'title' : 'Overall Performance',
    }
    return render(request, 'frontend/overall_performance.html', context)



def rotation_report(request):
    if request.user is None or not request.user.is_authenticated:
        machines = Machine.objects.none()
    else:
        machines = get_user_machines(request.user)
    print("user Machine Access: ", machines)

    # Get filters
    machine_filter = request.GET.get('machine', 29)
    shift_filter = request.GET.get('shift', '')
    from_datetime, to_datetime, datetime_from_formatted, datetime_to_formatted = get_datetime_range(request)

    # Base querysets
    rotation_qs = RotationStatus.objects.select_related('machine').filter(
        machine__in=machines,
        count_time__range=(from_datetime, to_datetime),
        # count_time__lte=to_datetime
    )
    npt_qs = ProcessedNPT.objects.select_related('machine', 'reason').filter(
        machine__in=machines,
        off_time__range=(from_datetime, to_datetime), 
        # on_time__gt=from_datetime
    )

    # Apply machine filter
    if machine_filter:
        rotation_qs = rotation_qs.filter(machine__mc_no=machine_filter)
        npt_qs = npt_qs.filter(machine__mc_no=machine_filter)

    # Determine shifts to process
    shifts = Shift.objects.all().order_by('start_time')
    selected_shifts = []
    if shift_filter:
        try:
            selected_shift = Shift.objects.get(id=int(shift_filter))
            selected_shifts = [selected_shift]
        except (Shift.DoesNotExist, ValueError, TypeError):
            pass
    else:
        # If no shift selected, use all shifts that overlap with date range
        for shift in shifts:
            selected_shifts.append(shift)

    # Skip null on_time except last
    npt_qs = skip_null_on_time_except_last(npt_qs)

    # --- Determine column structure ---
    use_4_columns = False
    for shift in selected_shifts:
        duration_sec = get_shift_duration_seconds(shift)
        if duration_sec <= 8 * 3600 + 60:  # Allow small tolerance
            use_4_columns = True
            break

    num_blocks = 4 if use_4_columns else 6
    ordinal_suffixes = ["st", "nd", "rd"] + ["th"] * 20
    block_headers = []
    for i in range(1, num_blocks + 1):
        suffix = ordinal_suffixes[i-1] if i <= 3 else "th"
        block_headers.append(f"{i}{suffix} 2h")

    # --- Process data for each shift instance ---
    all_shift_data = []
    for shift in selected_shifts:
        shift_instances = split_records_by_blocks_multi_day(
            rotation_qs, shift, from_datetime, to_datetime, num_blocks
        )
        all_shift_data.extend(shift_instances)

    # --- Aggregate table rows per shift ---
    table_rows = []
    for shift_instance in all_shift_data:
        shift_blocks = [block['total_count'] for block in shift_instance['blocks']]
        shift_total = sum(shift_blocks)
        
        # Get the effective start and end times for this specific shift instance
        shift_start_dt = shift_instance['effective_start']
        shift_end_dt = shift_instance['effective_end']
        
        # Calculate the total duration of the shift instance in minutes
        total_duration_minutes = (shift_end_dt - shift_start_dt).total_seconds() / 60.0
        
        # Calculate NPT that falls within this specific shift instance
        npt_minutes_for_shift = calculate_npt_minutes(shift_start_dt, shift_end_dt, npt_qs)
        
        # Calculate productive minutes
        productive_minutes = total_duration_minutes - npt_minutes_for_shift
        productive_minutes = max(0, productive_minutes)  # Ensure it's not negative
        
        # Calculate average RPM
        avg_rpm = 0
        if productive_minutes > 0:
            avg_rpm = shift_total / productive_minutes
        
        table_rows.append({
            'shift': shift_instance['shift_key'],
            'mc_no': '',  
            'blocks': shift_blocks,
            'avg_rpm': round(avg_rpm, 2),  
            'duration_minutes': round(total_duration_minutes, 2),
            'npt_minutes': round(npt_minutes_for_shift, 2),  
            'total': shift_total
        })

    # Get machine choices for filter
    if hasattr(machines, 'filter'):
        machine_choices = machines.filter(is_deleted=False).values_list('mc_no', flat=True).distinct().order_by('mc_no')
    else:
        machine_ids = [m.id for m in machines]
        machine_choices = Machine.objects.filter(
            id__in=machine_ids, 
            is_deleted=False
        ).values_list('mc_no', flat=True).distinct().order_by('mc_no')

    context = {
        'table_rows': table_rows,
        'block_headers': block_headers,
        'filter_machines': machine_choices,
        'filter_shifts': shifts,
        'selected_machine': machine_filter,
        'selected_shift': shift_filter,
        'datetime_from': datetime_from_formatted,
        'datetime_to': datetime_to_formatted,
        'machine_display': machine_filter or "All Machines",
        'date_display': f"{datetime_from_formatted} to {datetime_to_formatted}",
        'title': 'Shiftwise Roll Counter',
    }

    return render(request, 'frontend/rotation_report.html', context)
