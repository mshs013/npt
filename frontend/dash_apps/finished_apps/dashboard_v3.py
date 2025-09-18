# frontend/dash_apps/finished_apps/machine_dashboard.py
from dash import html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from core.models import ProcessedNPT, RotationStatus, Machine, NptReason
from library.models import Shift
from core.utils.utils import get_user_machines
from django.contrib.auth.models import AnonymousUser
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go


from frontend.utils.function_chart_helper import process_npt_to_hourly, get_reason_color_map
from frontend.utils.function_filter import skip_null_on_time_except_last
from frontend.utils.function_time import get_datetime_range

app = DjangoDash(
    "MachineDashboard_v3",
    serve_locally=True,
)

# ---------------------
# Formating Time from seconds (type = int)
# ---------------------
def format_seconds(total_seconds):
    """
    Convert seconds into a human-readable string.
    
    Examples:
    3665 -> "1h 1m 5s"
    65   -> "1m 5s"
    5    -> "5s"
    """
    
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{int(hours)}h")
    if minutes > 0 or hours > 0:  # show minutes if hours exist
        parts.append(f"{int(minutes)}m")
    parts.append(f"{int(seconds)}s")
    
    return " ".join(parts)


# -------------------
# Formating Time from seconds (type = pandas series)
# -------------------
def format_seconds_series(seconds_series):
    """
    Vectorized conversion of a pandas Series of seconds
    into human-readable H-M-S strings without decimals.
    Handles NaN or infinite values gracefully.
    """
    # Replace NaN or infinite values with 0 (or any placeholder you prefer)
    seconds_series = seconds_series.fillna(0).replace([np.inf, -np.inf], 0)
    
    # Round and convert to integer
    seconds_series = seconds_series.round().astype(int)

    hours = seconds_series // 3600
    minutes = (seconds_series % 3600) // 60
    seconds = seconds_series % 60

    formatted = (
        np.where(hours > 0, hours.astype(str) + "h ", "") +
        np.where((minutes > 0) | (hours > 0), minutes.astype(str) + "m ", "") +
        seconds.astype(str) + "s"
    )

    return formatted


def create_styled_table(df, header_color="primary", table_id=None):
    # print("inside styled Table: ", df)
    if df.empty:
        return html.Div("No data available.", className="text-center text-muted p-3")
    
    table = dbc.Table.from_dataframe(
        df,
        striped=True,
        bordered=True,
        hover=True,
        size="sm",
        className="table w-100 text-center",
        id=table_id,
        
    )
    
    return html.Div([
        table,
        html.Div(id=f"{table_id}-css" if table_id else None)
    ])




def clean_column_names(df, custom_mapping=None):
    """
    Convert underscored column names to proper title case names.
    
    Args:
        df: DataFrame with columns to rename
        custom_mapping: Dict of custom column name mappings
    
    Returns:
        DataFrame with cleaned column names
    """
    if custom_mapping is None:
        custom_mapping = {}
    
    # Default mapping for common patterns
    default_mapping = {
        'machine_label': 'Machine',
        'total_npt_formatted': 'Total NPT',
        'total_npt': 'Total NPT',
        'avg_npt_per_event_formatted': 'Avg NPT Per Event',
        'avg_npt_per_event': 'Avg NPT Per Event',
        'shift_name': 'Shift',
        'last_on_time': 'Last On Time',
        'last_activity': 'Last Activity',
        'min_time_event_formatted': 'Min Time Event',
        'max_time_event_formatted': 'Max Time Event',
        'events': 'Events',
        'efficiency': 'Efficiency (%)',
        'performance': 'Performance (%)',
        'status': 'Status',
        'reason': 'Reason',
        'machines': 'Machine'
    }
    
    # Combine mappings, with custom taking precedence
    mapping = {**default_mapping, **custom_mapping}
    
    # Apply mapping, falling back to title case for unmapped columns
    new_columns = {}
    for col in df.columns:
        if col in mapping:
            new_columns[col] = mapping[col]
        else:
            # Convert snake_case to Title Case
            new_columns[col] = col.replace('_', ' ').title()
    
    return df.rename(columns=new_columns)



# ---------------------
# AdminLTE Info Box
# ---------------------
def info_box(value, label, color="bg-info", icon="fas fa-cog", unit=""):
    return html.Div(
        className="info-box",
        children=[
            html.Span(
                className=f"info-box-icon {color} elevation-1",
                children=[html.I(className=icon)]
            ),
            html.Div(
                className="info-box-content",
                children=[
                    html.Span(className="info-box-text", children=label),
                    html.Span(
                        className="info-box-number",
                        children=[value, html.Small(unit)] if unit else value
                    )
                ]
            )
        ]
    )

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


# ---------------------
# Generate Data (function called inside callback)
# ---------------------
def generate_dashboard_data(request, user=None):
    # Fetch machines user has access to
    if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
        machines = Machine.objects.none()
    else:
        machines = get_user_machines(user)
    
    date_from, date_to, datetime_from_formatted, datetime_to_formatted = get_datetime_range(request)

    duration = date_to - date_from
    time_range_seconds = duration.total_seconds() 
    # --- RotationStatus queryset filtered by user machines and default datetime range ---
    rot_qs = RotationStatus.objects.select_related('machine').filter(
        machine__in=machines,
        count_time__gte=date_from,
        count_time__lte=date_to
    )

    # --- ProcessedNPT queryset filtered by user machines and default datetime range ---
    npt_qs = ProcessedNPT.objects.select_related('machine', 'reason').filter(
        machine__in=machines,
        off_time__gte=date_from,
        off_time__lte=date_to
    )

    # removing null values
    npt_qs = skip_null_on_time_except_last(npt_qs)

    # ---------------------
    # Prepare DataFrames using the new structure
    # ---------------------
    npt_df = pd.DataFrame([{
        "machine_id": npt.machine.id if npt.machine else None,
        "machine_label": f"{npt.machine.mc_no}" if npt.machine else "Unknown",
        "reason": npt.reason.name if npt.reason else "N/A",
        "off_time": npt.off_time,
        "on_time": npt.on_time
    } for npt in npt_qs])

    rot_df = pd.DataFrame([{
        "machine_id": rot.machine.id if rot.machine else None,
        "machine_label": f"{rot.machine.mc_no}" if rot.machine else "Unknown",
        "count": rot.count,
        "count_time": rot.count_time
    } for rot in rot_qs])

    # Ensure datetime conversion
    if not npt_df.empty:
        npt_df['off_time'] = pd.to_datetime(npt_df['off_time'])
        npt_df['on_time'] = pd.to_datetime(npt_df['on_time'])
    if not rot_df.empty:
        rot_df['count_time'] = pd.to_datetime(rot_df['count_time'])

    # ---------------------
    # Determine shift
    # ---------------------
    shifts = Shift.objects.all()

    # Replace your get_shift function with this simpler version:
    def get_shift(dt):
        dt_time = dt.time()
        
        for s in shifts:
            start_time = s.start_time
            end_time = s.end_time
            
            if start_time <= end_time:
                # Regular shift (same day)
                if start_time <= dt_time <= end_time:
                    return s.name
            else:
                # Overnight shift
                if dt_time >= start_time or dt_time <= end_time:
                    return s.name
        
        return "Unknown"

    if not npt_df.empty:
        npt_df['shift_name'] = npt_df['off_time'].apply(get_shift)

        # ---------------------
        # Calculate NPT duration in seconds
        # ---------------------
        npt_df['npt_time'] = npt_df.apply(
            lambda row: (row['on_time'] - row['off_time']).total_seconds() 
            if row['on_time'] is not pd.NaT else (pd.Timestamp.now() - row['off_time']).total_seconds(),
            axis=1
        )

        npt_df['npt_time_formatted'] = format_seconds_series(npt_df['npt_time'])
    else:
        npt_df['shift_name'] = []
        npt_df['npt_time'] = []
        npt_df['npt_time_formatted'] = []

    # ---------------------
    # Overall Metrics
    # ---------------------
    total_npt = npt_df['npt_time'].sum() if not npt_df.empty else 0
    total_events = len(npt_df)
    
    # Get list of inactive machines
    active_machines = set(npt_df['machine_id'].dropna()) if not npt_df.empty else set()
    all_machine_ids = set(machines.values_list('id', flat=True))
    inactive_machines = all_machine_ids - active_machines
    # print(active_machines)
    # print(all_machine_ids)
    # print(inactive_machines)
    # Create inactive machines DataFrame
    inactive_machines_df = pd.DataFrame()
    if inactive_machines:
        inactive_machines_data = []
        for machine in machines.filter(id__in=inactive_machines):
            # Find the last activity (most recent on_time) for this machine
            last_npt = ProcessedNPT.objects.filter(
                machine=machine,
                on_time__isnull=False
            ).order_by('-on_time').first()
            # print("last Active: ", last_npt, "-->", last_npt.on_time)
            if last_npt and last_npt.on_time:
                # Calculate time since last activity
                time_since_last = pd.Timestamp.now() - pd.Timestamp(last_npt.on_time)
                days = time_since_last.days
                hours = time_since_last.seconds // 3600
                minutes = (time_since_last.seconds % 3600) // 60
                
                if days > 0:
                    last_activity = f"{days}d {hours}h {minutes}m ago"
                elif hours > 0:
                    last_activity = f"{hours}h {minutes}m ago"
                else:
                    last_activity = f"{minutes}m ago"
                    
                last_on_time = last_npt.on_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                last_activity = 'No recorded activity'
                last_on_time = 'Never'
            
            inactive_machines_data.append({
                'machines': f"{machine.mc_no}",
                'last_on_time': last_on_time,
                'last_activity': last_activity
            })
        inactive_machines_df = pd.DataFrame(inactive_machines_data)
    # print(inactive_machines_df)
    rolls_produced_total = (npt_df['reason'] == "Roll Cutting").sum() if not npt_df.empty else 0
    # now = datetime.now()
    currentTimeInSeconds = time_range_seconds
    currentTimeInSecondsForAllMachines = currentTimeInSeconds * len(active_machines) if len(active_machines) > 0 else 1
    overall_npt_percent = round(((total_npt)/currentTimeInSecondsForAllMachines)*100, 2) if currentTimeInSecondsForAllMachines > 0 else 0
    overall_pt_percent = round(100 - overall_npt_percent, 2)
    total_avg_npt_all_machine = 0
    total_avg_event_all_machine = 0
    # ---------------------
    # Initialize empty figures and tables
    # ---------------------
    figs = {}
    machine_summary_table = html.Div("No data available for machines.", className="text-center")
    shift_summary_table = html.Div("No data available for shifts.", className="text-center")
    npt_summary_table = html.Div("No data available for NPT reasons.", className="text-center")
    
    if not inactive_machines_df.empty:
            # print("hello")
            inactive_machines_table = create_styled_table(
                clean_column_names(inactive_machines_df),
                header_color="danger",
                table_id="inactive-machines-table"
            )
    else:
            inactive_machines_table = html.Div(
                "No inactive machines found.", 
                className="text-center text-success p-3"
            )
    
    if not npt_df.empty:
        # ---------------------
        # Aggregations for figures and tables
        # ---------------------
        # Machine-level metrics
        machine_summary = npt_df.groupby('machine_label', as_index=False).agg(
            total_npt=('npt_time', 'sum'),
            events=('machine_label', 'count'),
            rolls_produced=('reason', lambda x: (x == "Roll Cutting").sum()),
            avg_npt_per_event=('npt_time', 'mean')  # Mean of individual events for accuracy
        )
        machine_summary['avg_npt_per_event'] = machine_summary['avg_npt_per_event'].round(2)
        machine_summary['efficiency'] = round(((currentTimeInSeconds - machine_summary['total_npt'])/currentTimeInSeconds) * 100, 2)
        machine_summary['status'] = machine_summary['efficiency'].apply(lambda x: "Good" if x > 70 else "Warning")
        machine_summary['performance'] = machine_summary['efficiency'].round(2)
        machine_summary['total_npt_formatted'] = format_seconds_series(machine_summary['total_npt'])
        machine_summary['avg_npt_per_event_formatted'] = format_seconds_series(machine_summary['avg_npt_per_event'])

        # ---------------------
        # Total/Average metrics for all machines
        # ---------------------
        total_npt_all_machines = machine_summary['total_npt'].sum()
        total_events_all_machines = machine_summary['events'].sum()
        
        total_avg_npt_all_machine = round(total_npt_all_machines / len(machine_summary), 2) if len(machine_summary) > 0 else 0
        total_avg_event_all_machine = round(total_events_all_machines / len(machine_summary), 2) if len(machine_summary) > 0 else 0
        
        # Optionally format to seconds for display
        # total_avg_npt_all_machine_formatted = format_seconds(total_avg_npt_all_machine)


        # Shift-level metrics

        shift_summary = npt_df.groupby('shift_name', as_index=False).agg(
            total_npt=('npt_time', 'sum'),
            events=('shift_name', 'count'),
            avg_npt_per_event=('npt_time', 'mean')
        )
        shift_summary['avg_npt_per_event'] = shift_summary['avg_npt_per_event'].round(2)
        
        # NEW: Calculate performance using actual shift duration
        # Create a mapping of shift names to their durations
        shift_duration_map = {}
        for shift in shifts:
            shift_duration_map[shift.name] = get_shift_duration_seconds(shift)
        
        # Apply the correct performance calculation
        def calculate_shift_performance(row):
            shift_name = row['shift_name']
            total_npt = row['total_npt']
            
            if shift_name in shift_duration_map:
                shift_duration = shift_duration_map[shift_name]*len(active_machines)
                # print("shift Duration: ", shift_duration_map[shift_name])
                # print("Shift Duration for all machines: ", shift_duration)
                # Performance = (Productive Time / Total Shift Time) * 100
                # Productive Time = Shift Duration - NPT Time
                performance = ((shift_duration - total_npt) / shift_duration) * 100
                return round(performance, 2)
            else:
                # Fallback to original calculation if shift not found
                return round(((currentTimeInSeconds - total_npt)/currentTimeInSeconds) * 100, 2)
        
        shift_summary['performance'] = shift_summary.apply(calculate_shift_performance, axis=1)
        shift_summary['total_npt_formatted'] = format_seconds_series(shift_summary['total_npt'])
        shift_summary['avg_npt_per_event_formatted'] = format_seconds_series(shift_summary['avg_npt_per_event'])

        # Machine + shift breakdown
        machine_shift_summary = npt_df.groupby(['machine_label', 'shift_name'], as_index=False)['npt_time'].sum()
        machine_shift_summary['npt_time_formatted'] = format_seconds_series(machine_shift_summary['npt_time'])

        # Average NPT per machine for figures
        machine_avg_summary = npt_df.groupby('machine_label', as_index=False)['npt_time'].mean()
        machine_avg_summary['npt_time'] = machine_avg_summary['npt_time'].round(2)
        machine_avg_summary['npt_time_formatted'] = format_seconds_series(machine_avg_summary['npt_time'])

        # Shift trend over time
        shift_trend_summary = npt_df.groupby(['shift_name', 'off_time'], as_index=False)['npt_time'].sum()
        shift_trend_summary['npt_time_formatted'] = format_seconds_series(shift_trend_summary['npt_time'])

        # ---------------------
        # Figures
        # ---------------------

        # get reason-color mappings
        reason_color_map = get_reason_color_map(NptReason)


        # Global labels for consistent axis and legend naming
        common_labels = {
            "machine_label": "Machine",
            "Machine Number": "Machine",
            "npt_time": "NPT",
            "reason": "Reason",
            "shift_name": "Shift",
            "total_npt": "Total NPT",
            "count_time":"Hour of Day",
            "count":"Count",
            "avg_npt_per_event": "Avg NPT per Event",
        }


        # NPT by Machine - with annotations
        fig_npt_by_machine = px.bar(
            machine_summary,
            x='machine_label', y='total_npt',
            title="NPT by Machine",
            hover_data={"total_npt": False},
            custom_data=['total_npt_formatted'],
            labels=common_labels

        )
        fig_npt_by_machine.update_traces(
            hovertemplate='<b>Machine: %{x}</b><br>NPT Time: %{customdata[0]}<br><extra></extra>'
        )
        # Add annotations for each bar
        # for i, row in machine_summary.iterrows():
        #     fig_npt_by_machine.add_annotation(
        #         x=row['machine_label'],
        #         y=row['total_npt'],
        #         text=f"{row['total_npt_formatted']}",
        #         showarrow=False,
        #         yshift=10,
        #         font=dict(size=10, color="black")
        #     )

        # Stacked Machine-Reason bar chart
        npt_machine_reason = npt_df.groupby(['machine_label', 'reason'])['npt_time'].sum().reset_index()
        npt_machine_reason['npt_time_formatted'] = format_seconds_series(npt_machine_reason['npt_time'])

        fig_npt_by_machine_reason = px.bar(
            npt_machine_reason,
            x="machine_label",
            y="npt_time",
            color="reason",
            title="NPT by Machine (Stacked by Reason)",
            labels=common_labels,
            custom_data=["npt_time_formatted"],
            color_discrete_map=reason_color_map  # Apply custom colors
        )

        fig_npt_by_machine_reason.update_traces(
            hovertemplate="<b>Machine:</b> %{x}<br>"
                        "<b>Reason:</b> %{fullData.name}<br>"
                        "<b>NPT Time:</b> %{customdata[0]}<extra></extra>"
        )

        fig_npt_by_machine_reason.update_layout(
            xaxis_title="Machine Number",
            yaxis_title="NPT Time",
            legend_title="Reason"
        )

        # NPT by Reason - Pie Chart (no annotations needed for pie charts)
        npt_reason_summary = npt_df.groupby('reason')['npt_time'].sum().reset_index()
        npt_reason_summary['npt_time_formatted'] = format_seconds_series(npt_reason_summary['npt_time'])
        
        fig_npt_by_reason_pie = px.pie(
            npt_reason_summary,
            names='reason', 
            values='npt_time',
            title="NPT by Reasons",
            labels=common_labels,
            color='reason',
            color_discrete_map=reason_color_map  # Apply custom colors
        )
        
        # Update hover template with formatted time
        fig_npt_by_reason_pie.update_traces(
            hovertemplate='<b>%{label}</b><br>NPT Time: %{customdata[0]}<br>Percentage: %{percent}<br><extra></extra>',
            customdata=npt_reason_summary['npt_time_formatted']
        )

        # NPT by Reason - Bar Chart - with annotations
        npt_grouped = npt_df.groupby('reason')['npt_time'].sum().reset_index()
        npt_grouped["npt_time_formatted"] = format_seconds_series(npt_grouped['npt_time'])
        
        fig_npt_by_reason_bar = px.bar(
            npt_grouped,
            x='reason', 
            y='npt_time',
            title="NPT by Reasons",
            color='reason',
            custom_data=[npt_grouped['npt_time_formatted']],
            labels=common_labels,
            color_discrete_map=reason_color_map  # Apply custom colors
        )
        
        fig_npt_by_reason_bar.update_traces(
            hovertemplate='<b>%{label}</b><br>NPT Time: %{customdata[0]}<br><extra></extra>'
        )
        # Add annotations for each bar
        # for i, row in npt_grouped.iterrows():
        #     fig_npt_by_reason_bar.add_annotation(
        #         x=row['reason'],
        #         y=row['npt_time'],
        #         text=f"{row['npt_time_formatted']}",
        #         showarrow=False,
        #         yshift=10,
        #         font=dict(size=10, color="black")
        #     )


        # Use .copy() to prevent a SettingWithCopyWarning from pandas
        hourly_npt_df = process_npt_to_hourly(npt_df.copy())

        fig_hourly_trend = go.Figure()

        if not hourly_npt_df.empty:
            for mc, df_mc in hourly_npt_df.groupby("machine_label"):
                # Ensure data covers all 24 hours for a continuous line, filling
                # missing hours with 0 NPT.
                hours_of_day = np.arange(24)
                machine_data = df_mc.set_index("hour").reindex(hours_of_day, fill_value=0)

                # Add one line per machine
                fig_hourly_trend.add_trace(go.Scatter(
                    x=machine_data.index,              # X-axis: Hours from 0 to 23
                    y=machine_data["npt_seconds"],    # Y-axis: NPT in seconds
                    mode="lines+markers",             # Lines + markers (better hover target)
                    name=mc,                          # Legend entry = machine name
                    line=dict(width=2, shape="spline"),  # Smooth curve
                    marker=dict(size=6),              # Markers make hover easier
                    customdata=[mc] * 24,             # Pass machine name for hover
                    hovertemplate=(                   # Tooltip shown when hovering over line/marker
                        "<b>Machine:</b> %{customdata}"
                        "<br><b>Hour:</b> %{x}:00 - %{x}:59"
                        "<br><b>NPT:</b> %{y:.0f} seconds"
                        "<extra></extra>"
                    )
                ))

        # ---------------------
        # Layout / Axis Settings
        # ---------------------
        fig_hourly_trend.update_layout(
            title_text="<b>Hourly NPT Trend</b>",
            xaxis_title="Hour of Day",
            yaxis_title="NPT",
            legend_title="Machine",
            
            # Only show tooltip when hovering directly over a line/marker
            hovermode="closest",

            # X-axis: ticks every 2 hours, cover full 0–23 range
            xaxis=dict(
                tickmode="array",
                tickvals=np.arange(0, 24, 2),
                range=[0, 23]
            ),
            
            # Y-axis: fixed from 0 to 3600 (1 hour), with friendly minute labels
            yaxis=dict(
                range=[0, 3600],
                tickmode="array",
                tickvals=[0, 600, 1200, 1800, 2400, 3000, 3600],
                ticktext=["0m", "10m", "20m", "30m", "40m", "50m", "60m"]
            )
        )

        # Machine NPT by Shift - with annotations
        fig_npt_by_shift = px.bar(
            machine_shift_summary,
            x='machine_label', y='npt_time', color='shift_name',
            title="Machine NPT by Shift",
            barmode='stack',
            hover_data={"npt_time": False},
            custom_data=['npt_time_formatted'],
            labels=common_labels
        )
        fig_npt_by_shift.update_traces(
            hovertemplate='<b>Machine: %{x}</b><br>Shift: %{fullData.name}<br>NPT Time: %{customdata[0]}<br><extra></extra>'
        )
        # Calculate total NPT per machine for annotations (for stacked bars)
        # machine_shift_totals = machine_shift_summary.groupby('machine_label')['npt_time'].sum()
        # for machine, total in machine_shift_totals.items():
        #     fig_npt_by_shift.add_annotation(
        #         x=machine,
        #         y=total,
        #         text=f"{format_seconds(total)}",
        #         showarrow=False,
        #         yshift=10,
        #         font=dict(size=10, color="black")
        #     )

        # Shiftwise NPT Distribution (pie chart, no annotations needed)
        fig_shiftwise_npt = px.pie(
            shift_summary,
            names='shift_name', values='total_npt',
            title="Shiftwise NPT Distribution",
            custom_data=['total_npt_formatted'],
            labels=common_labels
        )
        fig_shiftwise_npt.update_traces(
            hovertemplate='<b>%{label}</b><br>NPT Time: %{customdata[0]}<br>Percentage: %{percent}<br><extra></extra>'
        )

        # Average NPT per Machine - with annotations
        fig_machine_perf = px.bar(
            machine_avg_summary,
            x='machine_label', y='npt_time',
            title="Average NPT per Machine",
            hover_data={"npt_time": False},
            custom_data=['npt_time_formatted'],
            labels=common_labels
        )
        fig_machine_perf.update_traces(
            hovertemplate='<b>Machine: %{x}</b><br>Avg NPT Time: %{customdata[0]}<br><extra></extra>'
        )
        # Add annotations for each bar
        # for i, row in machine_avg_summary.iterrows():
        #     fig_machine_perf.add_annotation(
        #         x=row['machine_label'],
        #         y=row['npt_time'],
        #         text=f"{row['npt_time_formatted']}",
        #         showarrow=False,
        #         yshift=10,
        #         font=dict(size=10, color="black")
        #     )

        # Shiftwise NPT Trend (line chart, no annotations needed)
        fig_shiftwise_trend = px.line(
            shift_trend_summary,
            x='off_time', y='npt_time', color='shift_name',
            title="Shiftwise NPT Overview",
            hover_data={"npt_time": False},
            custom_data=['npt_time_formatted'],
            labels=common_labels
        )
        fig_shiftwise_trend.update_traces(
            hovertemplate='<b>Time: %{x}</b><br>Shift: %{fullData.name}<br>NPT Time: %{customdata[0]}<br><extra></extra>'
        )

        figs = {
            "fig_npt_by_machine": fig_npt_by_machine,
            "fig_npt_by_machine_reason": fig_npt_by_machine_reason,
            "fig_npt_by_reason_pie": fig_npt_by_reason_pie,
            "fig_npt_by_reason_bar": fig_npt_by_reason_bar,
            "fig_hourly_trend": fig_hourly_trend,
            "fig_npt_by_shift": fig_npt_by_shift,
            "fig_shiftwise_npt": fig_shiftwise_npt,
            "fig_machine_perf": fig_machine_perf,
            "fig_shiftwise_trend": fig_shiftwise_trend,
        }

        # ---------------------
        # Tables
        # ---------------------

        # inactive machines table - using dbc.Table

        # updating machine_summary for table
        columns_to_show_machine = [
            'machine_label',
            'total_npt_formatted',
            'events',
            'avg_npt_per_event_formatted',
            'efficiency',
            'status'
        ]

        machine_summary_display = machine_summary[columns_to_show_machine].rename(columns={
            'machine_label': 'Machine',
            'total_npt_formatted': 'Total NPT',
            'avg_npt_per_event_formatted': 'Avg NPT Per Event'
        })

        # Updating shift_summary for table
        columns_to_show_shift = [
            'shift_name',
            'total_npt_formatted',
            'events',
            'avg_npt_per_event_formatted',
            'performance'
        ]

        shift_summary_display = shift_summary[columns_to_show_shift].rename(columns={
            'shift_name': 'Shift',
            'total_npt_formatted': 'Total NPT',
            'avg_npt_per_event_formatted': 'Avg NPT Per Event'
        })

        # Machine summary table - using dbc.Table
        machine_summary_table = create_styled_table(
            clean_column_names(machine_summary_display),
            header_color="primary",
            table_id="machine-summary-table"
        )

        # Shift summary table - using dbc.Table
        shift_summary_table = create_styled_table(
            clean_column_names(shift_summary_display),
            header_color="success",
            table_id="shift-summary-table"
        )

        # Machine-Reason table
        # Create summary table with additional statistics
        npt_summary_stats = npt_df.groupby('reason').agg({
            'npt_time': ['sum', 'count', 'mean', 'min', 'max']
        }).round(2)

        # Flatten column names
        npt_summary_stats.columns = ['total_npt', 'events', 'avg_time_per_event', 'min_time_event', 'max_time_event']

        # Reset index to make reason a column
        npt_summary_stats = npt_summary_stats.reset_index()

        # Apply formatting to time columns
        time_columns = ['total_npt', 'avg_time_per_event', 'min_time_event', 'max_time_event']
        for col in time_columns:
            npt_summary_stats[f'{col}_formatted'] = npt_summary_stats[col].apply(format_seconds)
            
        # Create display table with formatted times
        npt_display_table = npt_summary_stats[['reason', 'total_npt_formatted', 'events', 'avg_time_per_event_formatted', 'min_time_event_formatted', 'max_time_event_formatted']].copy()
        npt_display_table.columns = ['reason', 'total_npt', 'events', 'avg_time_per_event', 'min_time_event', 'max_time_event']

        if not npt_summary_stats.empty:
            # Calculate NPT %
            npt_summary_stats['npt_percent'] = round((npt_summary_stats['total_npt'] / total_npt) * 100, 2) if total_npt > 0 else 0
            npt_summary_stats['total_npt_formatted'] = npt_summary_stats['total_npt'].apply(format_seconds)
            npt_summary_stats['avg_time_per_event_formatted'] = npt_summary_stats['avg_time_per_event'].apply(format_seconds)
            npt_summary_stats['min_time_event_formatted'] = npt_summary_stats['min_time_event'].apply(format_seconds)
            npt_summary_stats['max_time_event_formatted'] = npt_summary_stats['max_time_event'].apply(format_seconds)

            # Reorder columns: reason, total_npt, npt_percent, events, avg_time_per_event, min_time_event, max_time_event
            npt_display_table = npt_summary_stats[['reason', 'total_npt_formatted', 'npt_percent', 'events',
                                                'avg_time_per_event_formatted', 'min_time_event_formatted', 'max_time_event_formatted']].copy()
            npt_display_table.columns = ['Reason', 'Total NPT', 'NPT %', 'Events', 'Avg NPT Per Event', 'Min Time Event', 'Max Time Event']

            npt_summary_table = create_styled_table(
                npt_display_table,
                header_color="primary",
                table_id="npt-summary-table"
            )
        else:
            npt_summary_table = html.Div("No data available for NPT reasons.", className="text-center")
    else:
        # Empty figures when no data
        figs = {k: {} for k in [
            'fig_npt_by_machine', 'fig_npt_by_machine_reason', 'fig_npt_by_reason_pie',
            'fig_npt_by_reason_bar', 'fig_hourly_trend', 'fig_npt_by_shift',
            'fig_shiftwise_npt', 'fig_machine_perf', 'fig_shiftwise_trend'
        ]}

    # Hourly Rotation Counter Trend - handle rotation data
    if not rot_df.empty:
        figs['fig_hourly_trend_rotation'] = px.line(
            rot_df,
            x='count_time', y='count', color='machine_label',
            title="Hourly Rotation Counter Trend",
            labels=common_labels
        )
    else:
        figs['fig_hourly_trend_rotation'] = {}

    # ---------------------
    # Return
    # ---------------------
    return {
        "total_npt": total_npt,
        "total_events": total_events,
        "active_machines": len(active_machines),
        "inactive_machines": len(inactive_machines),
        "overall_npt_percent": overall_npt_percent,
        "overall_pt_percent": overall_pt_percent,
        "rolls_produced_total": rolls_produced_total,
        "total_avg_npt_all_machine_formatted":format_seconds(total_avg_npt_all_machine),
        "total_avg_event_all_machine":total_avg_event_all_machine,
        "figs": figs,
        "tables": {
            "machine_summary_table": machine_summary_table,
            "shift_summary_table": shift_summary_table,
            "npt_summary_table": npt_summary_table,
            "inactive_machines_table":inactive_machines_table
        }
    }


# ---------------------
# Layout
# ---------------------
app.layout = dbc.Container([
    dcc.Interval(id="interval-update", interval=60*1000),  # update every minute
    html.Div(id="dashboard-content")
], fluid=True)

# ---------------------
# Callback to update dashboard
# ---------------------
@app.callback(
    Output("dashboard-content", "children"),
    [Input("interval-update", "n_intervals")]
)
def update_dashboard(n_intervals, callback_context=None, request=None, user=None):
    # If the user isn't automatically inferred, default to AnonymousUser
    if not user or not user.is_authenticated:
        user = AnonymousUser()

    data = generate_dashboard_data(request, user=user)
    figs = data["figs"]
    tables = data["tables"]

    total_npt = data["total_npt"]
    total_events = data["total_events"]
    total_avg_event_all_machine = data["total_avg_event_all_machine"]
    total_avg_npt_all_machine = data["total_avg_npt_all_machine_formatted"]
    active_machines = data["active_machines"]
    inactive_machines = data["inactive_machines"]
    overall_npt_percent = data["overall_npt_percent"]
    overall_pt_percent = data["overall_pt_percent"]
    rolls_produced_total = data["rolls_produced_total"]

    return dbc.Container([
        # Cards Row 1
        dbc.Row([
            dbc.Col([
                info_box(f"{format_seconds(total_npt)}", "Total NPT", "bg-info", "fas fa-clock", '')
            ], xs=12, sm=6, md=3, className="mb-3"),
            
            dbc.Col([
                info_box(str(total_events), "Total Events", "bg-warning", "fas fa-list", '')
            ], xs=12, sm=6, md=3, className="mb-3"),
            
            dbc.Col([
                info_box(str(active_machines), "Active Machines", "bg-primary", "fas fa-cogs", '')
            ], xs=12, sm=6, md=3, className="mb-3"),
            
            dbc.Col([
                info_box(str(inactive_machines), "Inactive Machines", "bg-secondary", "fas fa-power-off", '')
            ], xs=12, sm=6, md=3, className="mb-3"),
        ], className="g-3 mb-4"),
        
        # Cards Row 2
        dbc.Row([            
            dbc.Col([
                info_box(str(total_avg_event_all_machine), "Avg Events for All Machines", "bg-danger", "fas fa-chart-bar", '')
            ], xs=12, sm=6, md=3, className="mb-3"),
            dbc.Col([
                info_box(f"{total_avg_npt_all_machine}", "Avg NPT for All Machines", "bg-danger", "fas fa-tachometer-alt", '')
            ], xs=12, sm=6, md=3, className="mb-3"),
            
            dbc.Col([
                info_box(f"{overall_npt_percent}%", "Overall NPT %", "bg-info", "fas fa-exclamation-triangle", '')
            ], xs=12, sm=6, md=3, className="mb-3"),
            
            dbc.Col([
                info_box(f"{rolls_produced_total}", "Rolls Produced", "bg-secondary", "fas fa-industry", '')
            ], xs=12, sm=6, md=3, className="mb-3"),
        ], className="g-3 mb-4"),

        # Charts Row 1 - Machine Charts
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            dcc.Graph(
                                figure=figs.get("fig_npt_by_machine", {}), 
                                style={"height":"400px"},
                                config={'responsive': True, 'displayModeBar': False}
                            )
                        ], style={"overflow-x": "auto"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], xs=12, sm=12, md=6, lg=4, className="mb-4"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            dcc.Graph(
                                figure=figs.get("fig_machine_perf", {}), 
                                style={"height":"400px"},
                                config={'responsive': True, 'displayModeBar': False}
                            )
                        ], style={"overflow-x": "auto"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], xs=12, sm=12, md=6, lg=4, className="mb-4"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            dcc.Graph(
                                figure=figs.get("fig_npt_by_machine_reason", {}), 
                                style={"height":"400px"},
                                config={'responsive': True, 'displayModeBar': False}
                            )
                        ], style={"overflow-x": "auto"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], xs=12, sm=12, md=6, lg=4, className="mb-4"),
        ], className="g-3"),

        # Hourly Trend Chart
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            dcc.Graph(
                                figure=figs.get("fig_hourly_trend", {}), 
                                style={"height":"400px"},
                                config={'responsive': True, 'displayModeBar': False}
                            )
                        ], style={"overflow-x": "auto"})
                    ], className="p-0")
                ], className="shadow-sm border-0")
            ], xs=12, className="mb-4")
        ]),

        # Reason Charts
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            dcc.Graph(
                                figure=figs.get("fig_npt_by_reason_bar", {}), 
                                style={"height":"400px"},
                                config={'responsive': True, 'displayModeBar': False}
                            )
                        ], style={"overflow-x": "auto"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], xs=12, sm=12, md=6, className="mb-4"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            dcc.Graph(
                                figure=figs.get("fig_npt_by_reason_pie", {}), 
                                style={"height":"400px"},
                                config={'responsive': True, 'displayModeBar': False}
                            )
                        ], style={"overflow-x": "auto"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], xs=12, sm=12, md=6, className="mb-4"),
        ], className="g-3"),

        # Rotation Counter Chart
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            dcc.Graph(
                                figure=figs.get("fig_hourly_trend_rotation", {}), 
                                style={"height":"400px"},
                                config={'responsive': True, 'displayModeBar': False}
                            )
                        ], style={"overflow-x": "auto"})
                    ], className="p-0")
                ], className="shadow-sm border-0")
            ], xs=12, className="mb-4")
        ]),

        # Shift Charts
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            dcc.Graph(
                                figure=figs.get("fig_shiftwise_trend", {}), 
                                style={"height":"400px", "min-width": "700px"},
                                config={'responsive': True, 'displayModeBar': False}
                            )
                        ], style={"overflow-x": "auto", "overflow-y": "hidden"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], xs=12, sm=12, md=12, lg=6, className="mb-4"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            dcc.Graph(
                                figure=figs.get("fig_npt_by_shift", {}), 
                                style={"height":"400px", "min-width": "350px"},
                                config={'responsive': True, 'displayModeBar': False}
                            )
                        ], style={"overflow-x": "auto", "overflow-y": "hidden"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], xs=12, sm=6, md=6, lg=3, className="mb-4"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            dcc.Graph(
                                figure=figs.get("fig_shiftwise_npt", {}), 
                                style={"height":"400px", "min-width": "350px"},
                                config={'responsive': True, 'displayModeBar': False}
                            )
                        ], style={"overflow-x": "auto", "overflow-y": "hidden"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], xs=12, sm=6, md=6, lg=3, className="mb-4"),
        ], className="g-3"),

        # Tables Section
        dbc.Row([
            # Machine Summary Table
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Machinewise Performance Summary", className="mb-0 text-dark fw-bold")
                    ], className="bg-light border-bottom"),
                    dbc.CardBody([
                        html.Div([
                            tables["machine_summary_table"]
                        ], style={
                            "overflow-x": "auto",
                            "overflow-y": "auto",
                            "max-height": "500px"
                        }, className="table-responsive")
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], xs=12, sm=12, md=12, lg=8, className="mb-4"),
            
            # Inactive Machines Table
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Inactive Machines List", className="mb-0 text-dark fw-bold")
                    ], className="bg-light border-bottom"),
                    dbc.CardBody([
                        html.Div([
                            tables["inactive_machines_table"]
                        ], style={
                            "overflow-x": "auto",
                            "overflow-y": "auto",
                            "max-height": "500px"
                        }, className="table-responsive")
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], xs=12, sm=12, md=12, lg=4, className="mb-4"),
        ], className="g-3"),

        # Shift Summary Table
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Shiftwise Performance Summary", className="mb-0 text-dark fw-bold")
                    ], className="bg-light border-bottom"),
                    dbc.CardBody([
                        html.Div([
                            tables["shift_summary_table"]
                        ], style={
                            "overflow-x": "auto",
                            "overflow-y": "auto",
                            "max-height": "500px"
                        }, className="table-responsive")
                    ], className="p-0")
                ], className="shadow-sm border-0")
            ], xs=12, className="mb-4")
        ]),

        # Reason Summary Table
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Reasonwise NPT Summary", className="mb-0 text-dark fw-bold")
                    ], className="bg-light border-bottom"),
                    dbc.CardBody([
                        html.Div([
                            tables["npt_summary_table"]
                        ], style={
                            "overflow-x": "auto",
                            "overflow-y": "auto",
                            "max-height": "500px"
                        }, className="table-responsive")
                    ], className="p-0")
                ], className="shadow-sm border-0")
            ], xs=12, className="mb-4")
        ])
    ], fluid=True, className="py-4") 