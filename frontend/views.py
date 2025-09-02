from django.shortcuts import render
from core.middleware import skip_permission
from django.http import JsonResponse, HttpResponse
from datetime import datetime, date, time, timedelta
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

from frontend.utils.function_filter import get_current_shift_display, filter_by_shift, get_shift_for_time, get_shift_identifier, parse_filters_and_dates, apply_npt_filters
from frontend.utils.function_time import calculate_minutes_between, get_date_range, format_duration_hms, calculate_seconds_between
from frontend.utils.function_overall_performance_helper import generate_shift_table, generate_summary_table


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
    if request.user is None or isinstance(request.user, AnonymousUser) or not request.user.is_authenticated:
        machines = Machine.objects.none()
    else:
        machines = get_user_machines(request.user)

    # Get filter parameters from request
    machine_filter = request.GET.get('machine', '')
    reason_filter = request.GET.get('reason', '')
    shift_filter = request.GET.get('shift', '')

    # Set default date values
    current_date = date.today()
    current_datetime = datetime.now()
    default_date_from = current_date.strftime('%Y-%m-%dT00:00')
    default_date_to = current_datetime.strftime('%Y-%m-%dT%H:%M')  # Fixed format
    
    date_from = request.GET.get('date_from', default_date_from)
    date_to = request.GET.get('date_to', default_date_to)
    
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
            npt_records = npt_records.filter(reason__id=int(reason_filter))
        except (ValueError, TypeError):
            pass
    
    # Date filtering with better error handling
    if date_from:
        try:
            from_datetime = datetime.fromisoformat(date_from.replace('T', ' '))
            npt_records = npt_records.filter(off_time__gte=from_datetime)
        except ValueError:
            pass
    
    if date_to:
        try:
            to_datetime = datetime.fromisoformat(date_to.replace('T', ' '))
            npt_records = npt_records.filter(off_time__lte=to_datetime)
        except ValueError:
            pass
    
    # Shift filtering
    if shift_filter:
        try:
            shift = Shift.objects.get(id=int(shift_filter))
            npt_records = filter_by_shift(npt_records, shift)
        except (Shift.DoesNotExist, ValueError, TypeError):
            pass
    
    # Order by most recent first
    npt_records = npt_records.order_by('-off_time')
    
    # Calculate time range in seconds
    time_range_seconds = calculate_seconds_between(date_from, date_to)
    
    # Process data in single loop for efficiency
    reason_counts = {}
    machine_data = {}
    npt_data = []
    
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
        
        # Collect NPT data
        npt_data.append({
            "machine": machine_name,
            "reason": reason_name,
            "offTime": record.off_time,
            "onTime": record.on_time,
            "duration": duration
        })
    
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
        # print(machine_reasons)
        # Calculate NPT percentage
        npt_percentage = round((total_machine_npt / time_range_seconds) * 100, 2) if time_range_seconds > 0 else 0
        
        machines_list.append({
            "name": machine_name,
            "reasons": machine_reasons,
            "total_npt": format_duration_hms(round(total_machine_npt, 2)),
            "npt_percentage": npt_percentage,
        })
        
    # Get dropdown options for filters - Fixed: use correct filter
    machine_choices = machines.filter(is_deleted=False)  # Assuming SoftDeleteModel has is_deleted
    all_reasons = NptReason.objects.filter(is_deleted=False).order_by('name')
    
    # Calculate totals
    total_reason_counts = sum(reason['count'] for reason in reasons)
    
    context = {
        'reasons': reasons,
        'shifts': shifts,
        'machines': machines_list,
        'npt_data': npt_data,
        'total_npt_all': format_duration_hms(round(total_npt_all, 2)),
        'total_reason_counts': total_reason_counts,
        'time_range_minutes': time_range_seconds,
        # Filter options
        'filter_machines': machine_choices,
        'filter_reasons': all_reasons,
        'filter_shifts': all_shifts,
        'current_shift': get_current_shift_display(shift_filter),
        'footer_colspan': 2 + len(reasons),
        'title':'Machine Logs',
    }
    
    return render(request, 'frontend/mclogs.html', context)

@skip_permission
def mcgraph(request):
    """Render the NPT chart page"""
    return render(request, 'frontend/mcgraph.html')


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
def rotaionCounter(request):
    """
    View to display rotation counter data, correctly identifying rolls and calculating per-roll RPM.
    """
    # Fetch machines user has access to
    if request.user is None or isinstance(request.user, AnonymousUser) or not request.user.is_authenticated:
        machines = Machine.objects.none()
    else:
        machines = get_user_machines(request.user)

    print(machines)
    # Get filter parameters from request
    machine_filter = request.GET.get('machine', '')
    
    # Set default date values to today
    current_date = date.today()
    default_date_from = current_date.strftime('%Y-%m-%d')
    default_date_to = current_date.strftime('%Y-%m-%d')
    
    date_from_str = request.GET.get('date_from', default_date_from)
    date_to_str = request.GET.get('date_to', default_date_to)
    
    # Parse dates for filtering, with a fallback to today if parsing fails
    try:
        from_date = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        to_date = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        from_datetime = datetime.combine(from_date, time.min)
        to_datetime = datetime.combine(to_date, time.max)
    except (ValueError, TypeError):
        from_datetime = datetime.combine(current_date, time.min)
        to_datetime = datetime.combine(current_date, time.max)
        date_from_str = default_date_from
        date_to_str = default_date_to
    
    # Base queryset for rotation records - filter by user machines
    rotation_qs = RotationStatus.objects.select_related('machine').filter(
        machine__in=machines,
        count_time__gte=from_datetime,
        count_time__lte=to_datetime
    )
    
    # Base queryset for NPT records - filter by user machines
    npt_qs = ProcessedNPT.objects.select_related('machine', 'reason').filter(
        machine__in=machines,
        off_time__gte=from_datetime,
        off_time__lte=to_datetime
    )

    # Apply machine filter
    if machine_filter:
        try:
            rotation_qs = rotation_qs.filter(machine__id=int(machine_filter))
            npt_qs = npt_qs.filter(machine__id=int(machine_filter))
        except (ValueError, TypeError):
            pass

    # Fetch records ordered for processing rolls (chronologically per machine)
    rotation_records = rotation_qs.order_by('machine__mc_no', 'count_time')

    # --- New Roll Processing Logic ---
    all_rolls = []
    
    # Group records by machine object to process each machine's rolls separately
    for machine, machine_records_iter in groupby(rotation_records, key=lambda r: r.machine):
        if not machine:  # Skip records with no machine
            continue
            
        machine_records = list(machine_records_iter)
        mc_no = machine.mc_no
        
        current_roll_records = []
        roll_no_counter = 1

        for record in machine_records:
            # A new roll starts when count is 1.
            if record.count == 1 and current_roll_records:
                # Process the completed roll before starting the new one.
                start_record = current_roll_records[0]
                end_record = current_roll_records[-1]
                
                start_time = start_record.count_time
                end_time = end_record.count_time
                total_count = end_record.count

                duration = end_time - start_time
                duration_minutes = duration.total_seconds() / 60 if duration.total_seconds() > 0 else 0
                
                # Calculate NPT in minutes for the roll
                roll_npt = npt_qs.filter(
                    machine=machine,
                    off_time__gte=start_time,
                    off_time__lt=end_time
                )
                npt_minutes = sum(npt.get_duration().total_seconds() / 60 for npt in roll_npt)

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
                    'npt_minutes': round(npt_minutes, 2),
                    'avg_rpm': round(avg_rpm, 2)
                })
                roll_no_counter += 1
                
                current_roll_records = [record]
            else:
                current_roll_records.append(record)
        
        # After the loop, process the last remaining roll for the machine
        if current_roll_records:
            start_record = current_roll_records[0]
            end_record = current_roll_records[-1]
            
            start_time = start_record.count_time
            end_time = end_record.count_time
            total_count = end_record.count

            duration = end_time - start_time
            duration_minutes = duration.total_seconds() / 60 if duration.total_seconds() > 0 else 0

            # Calculate NPT in minutes for the roll
            roll_npt = npt_qs.filter(
                machine=machine,
                off_time__gte=start_time,
                off_time__lt=end_time
            )
            npt_minutes = sum(npt.get_duration().total_seconds() / 60 for npt in roll_npt)

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
                'npt_minutes': round(npt_minutes, 2),
                'avg_rpm': round(avg_rpm, 2)
            })

    # --- Prepare data for the template ---

    # 1. Intermediary Roll Data (sorted by start time, descending)
    intermediary_data = sorted(all_rolls, key=itemgetter('start_time'), reverse=True)
    for i, roll in enumerate(intermediary_data, 1):
        roll['serial_no'] = i

    machine_wise_summary = []
    machine_data = defaultdict(list)
    for roll in all_rolls:
        machine_data[roll['mc_no']].append(roll)

    for mc_no, rolls in machine_data.items():
        total_rolls = len(rolls)
        total_npt = sum(r['npt_minutes'] for r in rolls)
        overall_avg_rpm = sum(r['avg_rpm'] for r in rolls) / total_rolls if total_rolls else 0
        
        machine_wise_summary.append({
            'mc_no': mc_no,
            'avg_rpm': round(overall_avg_rpm, 2),
            'npt_minutes': round(total_npt, 2),
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

    # Get filter options for the dropdown - only machines user has access to
    if hasattr(machines, 'filter'):
        # machines is a QuerySet
        machine_choices = machines.filter(is_deleted=False).values_list('mc_no', flat=True).distinct().order_by('mc_no')
    else:
        # machines is a list/other iterable
        machine_choices = Machine.objects.filter(id__in=machines, is_deleted=False).values_list('mc_no', flat=True).distinct().order_by('mc_no')
    
    total_rolls_summary = sum(data['total_rolls'] for data in machine_wise_summary)
    
    context = {
        'machine_wise_summary': machine_wise_summary,
        'intermediary_data': intermediary_data,
        'rotation_log': rotation_log,
        'filter_machines': machine_choices,
        'selected_machine': machine_filter,
        'date_from': date_from_str,
        'date_to': date_to_str,
        'total_rolls': total_rolls_summary,
        'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'title':'Rotation Counter',
    }
    
    return render(request, 'frontend/rotation_counter.html', context)

### Report - daily performance

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

    # Set default date values
    current_date = date.today()
    default_date_from = current_date  # Start of today
    default_date_to = current_date  # Current time
    
    date_from = request.GET.get('date_from', default_date_from)
    date_to = request.GET.get('date_to', default_date_to)
    
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
    
    # Date filtering
    if date_from:
        try:
            if type(date_from) == str:
                date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            npt_records = npt_records.filter(off_time__date__gte=date_from)
        except ValueError:
            pass
    
    if date_to:
        try:
            if type(date_to) == str:
                date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
            # If same date, include the whole day
            if date_to == date_from:
                npt_records = npt_records.filter(off_time__date=date_to)
            else:
                npt_records = npt_records.filter(off_time__date__lte=date_to)
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
        'current_shift': get_current_shift_display(shift_filter),
        'footer_colspan': 2,
        # Plotly charts as HTML
        'bar_chart_html': bar_chart_html,
        'pie_chart_html': pie_chart_html,
        'donut_charts_html': donut_charts_html,
        'title':'Daily Performance',
    }
    
    return render(request, 'frontend/daily_performance.html', context)### Overall Performance

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

    if chart_data:
        df = pd.DataFrame(chart_data)
        daily_npt = df.groupby(['Date', 'Machine'])['NPT'].sum().reset_index()

        # Stacked Bar Chart with white background
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
            yaxis_range=[0, 24], 
            legend_title_text='Machines',
            margin=dict(l=40, r=20, t=40, b=20),
            plot_bgcolor='white',
            paper_bgcolor='white',
            xaxis=dict(
                gridcolor='lightgray',
                gridwidth=1,
                showgrid=True
            ),
            yaxis=dict(
                gridcolor='lightgray',
                gridwidth=1,
                showgrid=True
            )
        )
        bar_chart_html = fig_bar.to_html(full_html=False, include_plotlyjs='cdn')

        # Line Chart with curves and area fill
        fig_line = px.area(  # Changed from px.line to px.area for area effect
            daily_npt, 
            x='Date', 
            y='NPT', 
            color='Machine', 
            title='Daily NPT by Machine (Trend)',
            labels={'NPT': 'NPT (Min)', 'Date': 'Date'},
            height=400
        )
        
        # Update traces to add curves and adjust opacity
        fig_line.update_traces(
            line_shape='spline',  # Makes lines curved/smooth
            line=dict(width=1),   # Thicker lines
            fillcolor=None,       # Will be set individually below
            opacity=0.3           # Lower opacity for area fill
        )
        
        # Set individual opacity for each trace
        for i, trace in enumerate(fig_line.data):
            trace.update(
                line=dict(width=3, shape='spline'),
                fillcolor=trace.line.color.replace('rgb', 'rgba').replace(')', ', 0.3)') if 'rgb' in str(trace.line.color) else None
            )
        
        fig_line.update_layout(
            yaxis_range=[0, 24],  # Start from zero
            legend_title_text='Machines',
            margin=dict(l=40, r=20, t=40, b=20),
            plot_bgcolor='white',
            paper_bgcolor='white',
            xaxis=dict(
                gridcolor='lightgray',
                gridwidth=1,
                showgrid=True,
                zeroline=True,
                zerolinecolor='gray',
                zerolinewidth=1,
                dtick="D1",  # Show every day (D1 = 1 day interval)
                tickformat="%m/%d",  # Format as MM/DD
                tickangle=45,  # Rotate labels for better readability
                tickfont=dict(size=10)
            ),
            yaxis=dict(
                gridcolor='lightgray',
                gridwidth=1,
                showgrid=True,
                zeroline=True,
                zerolinecolor='gray',
                zerolinewidth=1
            )
        )
        line_chart_html = fig_line.to_html(full_html=False, include_plotlyjs='cdn')

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
        'title':'Overall Performance',
    }
    return render(request, 'frontend/overall_performance.html', context)