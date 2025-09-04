# frontend/dash_apps/finished_apps/machine_dashboard.py
from dash import html, dcc, dash_table
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
from core.models import ProcessedNPT, RotationStatus, Machine
from library.models import Shift
from core.utils.utils import get_user_machines
from django.contrib.auth.models import AnonymousUser
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date, time

from frontend.utils.function_chart_helper import process_npt_to_hourly

app = DjangoDash("MachineDashboard_v2", serve_locally=True)

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


# ---------------------
# Generate Data (function called inside callback)
# ---------------------
def generate_dashboard_data(user=None):
    # Fetch machines user has access to
    if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
        machines = Machine.objects.none()
    else:
        machines = get_user_machines(user)

    # Fetch NPT and Rotation data filtered by user's machines
    current_date = date.today()
    start_of_day = datetime.combine(current_date, time.min)
    end_of_day = datetime.combine(current_date, time.max)

    # Fetch NPT and Rotation data filtered by user's machines and current date
    npt_qs = ProcessedNPT.objects.select_related('machine', 'reason')\
        .filter(
            machine__in=machines,
            off_time__gte=start_of_day,
            off_time__lte=end_of_day
        )

    rot_qs = RotationStatus.objects.select_related('machine')\
        .filter(
            machine__in=machines,
            count_time__gte=start_of_day,
            count_time__lte=end_of_day
        )
    shifts = Shift.objects.all()

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
    def get_shift(dt):
        for s in shifts:
            start = pd.Timestamp(dt.date().strftime('%Y-%m-%d') + ' ' + s.start_time.strftime('%H:%M:%S'))
            end = pd.Timestamp(dt.date().strftime('%Y-%m-%d') + ' ' + s.end_time.strftime('%H:%M:%S'))
            if end < start:
                end += pd.Timedelta(days=1)
            if start <= dt <= end:
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
    print(active_machines)
    print(all_machine_ids)
    print(inactive_machines)
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

    rolls_produced_total = (npt_df['reason'] == "Roll Cutting").sum() if not npt_df.empty else 0
    now = datetime.now()
    currentTimeInSeconds = now.hour * 3600 + now.minute * 60 + now.second
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
    inactive_machines_table = html.Div("No data available for NPT reasons.", className="text-center")
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
        shift_summary['performance'] = round(((currentTimeInSeconds - shift_summary['total_npt'])/currentTimeInSeconds) * 100, 2)
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
        # NPT by Machine - with annotations
        fig_npt_by_machine = px.bar(
            machine_summary,
            x='machine_label', y='total_npt',
            title="NPT by Machine",
            hover_data={"total_npt": False},
            custom_data=['total_npt_formatted']
        )
        fig_npt_by_machine.update_traces(
            hovertemplate='<b>Machine: %{x}</b><br>NPT Time: %{customdata[0]}<br><extra></extra>'
        )
        # Add annotations for each bar
        for i, row in machine_summary.iterrows():
            fig_npt_by_machine.add_annotation(
                x=row['machine_label'],
                y=row['total_npt'],
                text=f"{row['total_npt_formatted']}",
                showarrow=False,
                yshift=10,
                font=dict(size=10, color="black")
            )

        # Stacked Machine-Reason bar chart
        npt_machine_reason = npt_df.groupby(['machine_label', 'reason'])['npt_time'].sum().reset_index()

        # Create pivot table for stacked bar chart
        npt_pivot = npt_machine_reason.pivot(index='machine_label', columns='reason', values='npt_time').fillna(0)
        
        # Calculate total NPT per machine for annotations
        machine_totals = npt_pivot.sum(axis=1)

        fig_npt_by_machine_reason = px.bar(
            npt_pivot,
            x=npt_pivot.index,
            y=npt_pivot.columns,
            title="NPT by Machine (Stacked by Reason)",
            labels={'x': 'Machine Number', 'value': 'NPT Time'},
        )
        fig_npt_by_machine_reason.update_traces(
            hovertemplate='<b>Reason: %{fullData.name}</b><br>Machine: %{x}<br>NPT Time: %{y}<br><extra></extra>'
        )
        # Add total annotations at the end of each bar
        for i, (machine, total) in enumerate(machine_totals.items()):
            fig_npt_by_machine_reason.add_annotation(
                x=machine,
                y=total,
                text=f"{format_seconds(total)}",
                showarrow=False,
                yshift=10,
                font=dict(size=10, color="black")
            )

        fig_npt_by_machine_reason.update_layout(
            xaxis_title="Machine Number",
            yaxis_title="NPT Time",
            legend_title="Reason"
        )

        # NPT by Reason - Pie Chart (no annotations needed for pie charts)
        fig_npt_by_reason_pie = px.pie(
            npt_df,
            names='reason', values='npt_time',
            title="NPT by Reasons",
            custom_data=[npt_df['npt_time_formatted']]
        )
        fig_npt_by_reason_pie.update_traces(
            hovertemplate='<b>%{label}</b><br>NPT Time: %{customdata[0]}<br>Percentage: %{percent}<br><extra></extra>'
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
            custom_data=[npt_grouped['npt_time_formatted']]
        )
        fig_npt_by_reason_bar.update_traces(
             hovertemplate='<b>%{label}</b><br>NPT Time: %{customdata[0]}<br><extra></extra>'
        )
        # Add annotations for each bar
        for i, row in npt_grouped.iterrows():
            fig_npt_by_reason_bar.add_annotation(
                x=row['reason'],
                y=row['npt_time'],
                text=f"{row['npt_time_formatted']}",
                showarrow=False,
                yshift=10,
                font=dict(size=10, color="black")
            )


        # Use .copy() to prevent a SettingWithCopyWarning from pandas
        hourly_npt_df = process_npt_to_hourly(npt_df.copy())

        fig_hourly_trend = go.Figure()

        if not hourly_npt_df.empty:
            for mc, df_mc in hourly_npt_df.groupby("machine_label"):
                # Ensure data covers all 24 hours for a continuous line, filling
                # missing hours with 0 NPT.
                hours_of_day = np.arange(24)
                machine_data = df_mc.set_index('hour').reindex(hours_of_day, fill_value=0)

                fig_hourly_trend.add_trace(go.Scatter(
                    x=machine_data.index,  # X-axis: Hours from 0 to 23
                    y=machine_data["npt_seconds"], # Y-axis: NPT in seconds
                    mode="lines",
                    name=mc,
                    line=dict(width=2, shape='spline'), # 'spline' creates a smooth curve
                    hovertemplate=(
                        "<b>Machine: %{customdata}</b>"
                        "<br>Hour: %{x}:00 - %{x}:59"
                        "<br>NPT: <b>%{y:.0f} seconds</b>"
                        "<extra></extra>"
                    ),
                    customdata=[mc] * 24 # Pass machine name to hover text
                ))



        # 3. Update the layout for a clean and informative chart
        fig_hourly_trend.update_layout(
            title_text="<b>Hourly NPT Trend</b>",
            xaxis_title="Hour of Day",
            yaxis_title="Non-Productive Time",
            legend_title="Machine",
            xaxis=dict(
                tickmode='array',
                tickvals=np.arange(0, 24, 2), # Show a tick every 2 hours
                range=[-0.0, 24] # Add padding to the x-axis for better visuals
            ),
            yaxis=dict(
                range=[0, 3600], # Y-axis fixed from 0 to 3600 seconds
                tickmode='array',
                tickvals=[0, 600, 1200, 1800, 2400, 3000, 3600],
                ticktext=['0m', '10m', '20m', '30m', '40m', '50m', '60m'] # User-friendly labels
            ),
            hovermode='x unified' # Great for comparing all machines at a specific hour
        )

        # Machine NPT by Shift - with annotations
        fig_npt_by_shift = px.bar(
            machine_shift_summary,
            x='machine_label', y='npt_time', color='shift_name',
            title="Machine NPT by Shift",
            barmode='stack',
            hover_data={"npt_time": False},
            custom_data=['npt_time_formatted']
        )
        fig_npt_by_shift.update_traces(
            hovertemplate='<b>Machine: %{x}</b><br>Shift: %{fullData.name}<br>NPT Time: %{customdata[0]}<br><extra></extra>'
        )
        # Calculate total NPT per machine for annotations (for stacked bars)
        machine_shift_totals = machine_shift_summary.groupby('machine_label')['npt_time'].sum()
        for machine, total in machine_shift_totals.items():
            fig_npt_by_shift.add_annotation(
                x=machine,
                y=total,
                text=f"{format_seconds(total)}",
                showarrow=False,
                yshift=10,
                font=dict(size=10, color="black")
            )

        # Shiftwise NPT Distribution (pie chart, no annotations needed)
        fig_shiftwise_npt = px.pie(
            shift_summary,
            names='shift_name', values='total_npt',
            title="Shiftwise NPT Distribution",
            custom_data=['total_npt_formatted']
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
            custom_data=['npt_time_formatted']
        )
        fig_machine_perf.update_traces(
            hovertemplate='<b>Machine: %{x}</b><br>Avg NPT Time: %{customdata[0]}<br><extra></extra>'
        )
        # Add annotations for each bar
        for i, row in machine_avg_summary.iterrows():
            fig_machine_perf.add_annotation(
                x=row['machine_label'],
                y=row['npt_time'],
                text=f"{row['npt_time_formatted']}",
                showarrow=False,
                yshift=10,
                font=dict(size=10, color="black")
            )

        # Shiftwise NPT Trend (line chart, no annotations needed)
        fig_shiftwise_trend = px.line(
            shift_trend_summary,
            x='off_time', y='npt_time', color='shift_name',
            title="Shiftwise NPT Overview",
            hover_data={"npt_time": False},
            custom_data=['npt_time_formatted']
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

        # inactive machines table
        if not inactive_machines_df.empty:
            inactive_machines_table = dash_table.DataTable(
                columns=[{"name": i.replace('_',' ').title(), "id": i} for i in inactive_machines_df.columns],
                data=inactive_machines_df.to_dict('records'),
                style_table={
                    'overflowX': 'auto',
                    'borderRadius': '8px',
                    'boxShadow': '0 2px 8px rgba(0,0,0,0.1)',
                    'border': '1px solid #e9ecef'
                },
                style_cell={
                    'textAlign': 'center', 
                    'padding': '12px 8px',
                    'fontSize': '14px',
                    'fontFamily': 'Arial, sans-serif',
                    'border': '1px solid #e9ecef'
                },
                style_header={
                    'backgroundColor': '#dc3545',
                    'color': 'white',
                    'fontWeight': 'bold',
                    'fontSize': '15px',
                    'textTransform': 'uppercase',
                    'letterSpacing': '0.5px',
                    'border': '1px solid #c82333'
                },
                style_data={
                    'backgroundColor': '#ffffff',
                    'color': '#2c3e50'
                },
                style_data_conditional=[
                    {
                        'if': {'row_index': 'odd'},
                        'backgroundColor': '#f8f9fa'
                    },
                    {
                        'if': {'state': 'active'},
                        'backgroundColor': '#f5c6cb',
                        'border': '1px solid #dc3545'
                    }
                ]
            )
        else:
            inactive_machines_table = html.Div("No inactive machines found.", className="text-center text-success")



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

        machine_summary_table = dash_table.DataTable(
            columns=[{"name": i.replace('_',' ').title(), "id": i} for i in machine_summary_display.columns],
            data=machine_summary_display.to_dict('records'),
            style_table={
                'overflowX': 'auto',
                'borderRadius': '8px',
                'boxShadow': '0 2px 8px rgba(0,0,0,0.1)',
                'border': '1px solid #e9ecef'
            },
            style_cell={
                'textAlign': 'center', 
                'padding': '12px 8px',
                'fontSize': '14px',
                'fontFamily': 'Arial, sans-serif',
                'border': '1px solid #e9ecef'
            },
            style_header={
                'backgroundColor': '#3498db',
                'color': 'white',
                'fontWeight': 'bold',
                'fontSize': '15px',
                'textTransform': 'uppercase',
                'letterSpacing': '0.5px',
                'border': '1px solid #2980b9'
            },
            style_data={
                'backgroundColor': '#ffffff',
                'color': '#2c3e50'
            },
            style_data_conditional=[
                {
                    'if': {'row_index': 'odd'},
                    'backgroundColor': '#f8f9fa'
                },
                {
                    'if': {'state': 'active'},
                    'backgroundColor': '#e3f2fd',
                    'border': '1px solid #2196f3'
                }
            ]
        )

        shift_summary_table = dash_table.DataTable(
            columns=[{"name": i.replace('_',' ').title(), "id": i} for i in shift_summary_display.columns],
            data=shift_summary_display.to_dict('records'),
            style_table={
                'overflowX': 'auto',
                'borderRadius': '8px',
                'boxShadow': '0 2px 8px rgba(0,0,0,0.1)',
                'border': '1px solid #e9ecef'
            },
            style_cell={
                'textAlign': 'center', 
                'padding': '12px 8px',
                'fontSize': '14px',
                'fontFamily': 'Arial, sans-serif',
                'border': '1px solid #e9ecef'
            },
            style_header={
                'backgroundColor': '#3498db',
                'color': 'white',
                'fontWeight': 'bold',
                'fontSize': '15px',
                'textTransform': 'uppercase',
                'letterSpacing': '0.5px',
                'border': '1px solid #229954'
            },
            style_data={
                'backgroundColor': '#ffffff',
                'color': '#2c3e50'
            },
            style_data_conditional=[
                {
                    'if': {'row_index': 'odd'},
                    'backgroundColor': '#f8f9fa'
                },
                {
                    'if': {'state': 'active'},
                    'backgroundColor': '#e8f5e8',
                    'border': '1px solid #27ae60'
                }
            ]
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

        # Create Dash DataTable
        npt_summary_table = dash_table.DataTable(
            columns=[{"name": i.replace('_',' ').title(), "id": i} for i in npt_display_table.columns],
            data=npt_display_table.to_dict('records'),
            style_table={
                'overflowX': 'auto',
                'borderRadius': '8px',
                'boxShadow': '0 2px 8px rgba(0,0,0,0.1)',
                'border': '1px solid #e9ecef'
            },
            style_cell={
                'textAlign': 'center', 
                'padding': '12px 8px',
                'fontSize': '14px',
                'fontFamily': 'Arial, sans-serif',
                'border': '1px solid #e9ecef'
            },
            style_header={
                'backgroundColor': '#3498db',
                'color': 'white',
                'fontWeight': 'bold',
                'fontSize': '15px',
                'textTransform': 'uppercase',
                'letterSpacing': '0.5px',
                'border': '1px solid #2980b9'
            },
            style_data={
                'backgroundColor': '#ffffff',
                'color': '#2c3e50'
            },
        )
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
            title="Hourly Rotation Counter Trend (Last 24h)"
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

    data = generate_dashboard_data(user=user)
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
            ], className="col-sm-6 col-md-3 mb-3", width=12),
            
            dbc.Col([
                info_box(str(total_events), "Total Events", "bg-warning", "fas fa-list", '')
            ], className="col-sm-6 col-md-3 mb-3", width=12),
            
            dbc.Col([
                info_box(str(active_machines), "Active Machines", "bg-primary", "fas fa-cogs", '')
            ], className="col-sm-6 col-md-3 mb-3", width=12),
            
            dbc.Col([
                info_box(str(inactive_machines), "Inactive Machines", "bg-secondary", "fas fa-power-off", '')
            ], className="col-sm-6 col-md-3 mb-3", width=12),
        ], className="g-3 mb-4"),
        
        # Cards Row 2
        dbc.Row([            
            dbc.Col([
                info_box(str(total_avg_event_all_machine), "Avg Events for All Machines", "bg-danger", "fas fa-chart-bar", '')
            ], className="col-sm-6 col-md-3 mb-3", width=12),
            dbc.Col([
                info_box(f"{total_avg_npt_all_machine}", "Avg NPT for All Machines", "bg-danger", "fas fa-tachometer-alt", '')
            ], className="col-sm-6 col-md-3 mb-3", width=12),
            
            dbc.Col([
                info_box(f"{overall_npt_percent}%", "Overall NPT %", "bg-info", "fas fa-exclamation-triangle", '')
            ], className="col-sm-6 col-md-3 mb-3", width=12),
            
            dbc.Col([
                info_box(f"{rolls_produced_total}", "Rolls Produced", "bg-secondary", "fas fa-industry", '')
            ], className="col-sm-6 col-md-3 mb-3", width=12),
        ], className="g-3 mb-4"),

        # Charts Row 1 - Machine Charts
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=figs.get("fig_npt_by_machine", {}), style={"height":"400px"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], width=12, className="col-sm-6 col-lg-4 col-md-6 mb-4"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=figs.get("fig_machine_perf", {}), style={"height":"400px"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], width=12, className="col-sm-6 col-lg-4 col-md-6 mb-4"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=figs.get("fig_npt_by_machine_reason", {}), style={"height":"400px"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], width=12, className="col-sm-6 col-lg-4 col-md-6 mb-4"),
        ], className="g-3"),

        # Hourly Trend Chart
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=figs.get("fig_hourly_trend", {}), style={"height":"400px"})
                    ], className="p-0")
                ], className="shadow-sm border-0")
            ], width=12, className="mb-4")
        ]),

        # Reason Charts
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=figs.get("fig_npt_by_reason_bar", {}), style={"height":"400px"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], width=12, className="col-sm-6 col-lg-6 col-md-6 mb-4"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=figs.get("fig_npt_by_reason_pie", {}), style={"height":"400px"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], width=12, className="col-sm-6 col-lg-6 col-md-6 mb-4"),
        ], className="g-3"),

        # Rotation Counter Chart
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=figs.get("fig_hourly_trend_rotation", {}), style={"height":"400px"})
                    ], className="p-0")
                ], className="shadow-sm border-0")
            ], width=12, className="mb-4")
        ]),

        # Shift Charts
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=figs.get("fig_shiftwise_trend", {}), style={"height":"400px"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], width=12, className="col-sm-6 col-lg-6 col-md-6 mb-4"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=figs.get("fig_npt_by_shift", {}), style={"height":"400px"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], width=12, className="col-sm-6 col-lg-3 col-md-6 mb-4"),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=figs.get("fig_shiftwise_npt", {}), style={"height":"400px"})
                    ], className="p-0")
                ], className="shadow-sm border-0 h-100")
            ], width=12, className="col-sm-6 col-lg-3 col-md-6 mb-4"),
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
                        tables["machine_summary_table"]
                    ], className="p-3")
                ], className="shadow-sm border-0 h-100")
            ], width=12, className="col-sm-6 col-lg-8 col-md-6 mb-4"),
            
            # Inactive Machines Table
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Inactive Machines List", className="mb-0 text-dark fw-bold")
                    ], className="bg-light border-bottom"),
                    dbc.CardBody([
                        tables["inactive_machines_table"]
                    ], className="p-3")
                ], className="shadow-sm border-0 h-100")
            ], width=12, className="col-sm-6 col-lg-4 col-md-6 mb-4"),
        ], className="g-3"),

        # Shift Summary Table
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Shiftwise Performance Summary", className="mb-0 text-dark fw-bold")
                    ], className="bg-light border-bottom"),
                    dbc.CardBody([
                        tables["shift_summary_table"]
                    ], className="p-3")
                ], className="shadow-sm border-0")
            ], width=12, className="mb-4")
        ]),

        # Reason Summary Table
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("Reasonwise NPT Summary", className="mb-0 text-dark fw-bold")
                    ], className="bg-light border-bottom"),
                    dbc.CardBody([
                        tables["npt_summary_table"]
                    ], className="p-3")
                ], className="shadow-sm border-0")
            ], width=12, className="mb-4")
        ])
    ], fluid=True, className="py-4")