# frontend/dash_apps/finished_apps/machine_dashboard.py
from dash import html, dcc, dash_table
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
import pandas as pd
import numpy as np
import plotly.express as px

from core.models import ProcessedNPT, RotationStatus, Machine
from library.models import Shift

app = DjangoDash("MachineDashboard", serve_locally=True)

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
# AdminLTE Table
# ---------------------
def info_table(df, title="", color="bg-info", icon="fas fa-cog", unit=""):
    """
    Convert a Pandas DataFrame into an AdminLTE-style info box table.
    Each cell will be a mini info-box.
    """
    if df.empty:
        return html.Div("No data available.", className="text-center")

    # Table header
    header = html.Tr([html.Th(col.replace("_", " ").title()) for col in df.columns])

    # Table body
    body = []
    for _, row in df.iterrows():
        cells = []
        for col in df.columns:
            val = row[col]
            cells.append(
                html.Td(
                    val
                )
            )
        body.append(html.Tr(cells))

    return html.Div([
        html.H5(title),
        html.Div(
            html.Table([html.Thead(header), html.Tbody(body)], className="table table-bordered"),
            className="table-responsive p-0"
        )
    ])

# ---------------------
# Generate Data
# ---------------------
def generate_dashboard_data():
    # Fetch data
    npt_qs = ProcessedNPT.objects.select_related('machine', 'reason').all()
    rot_qs = RotationStatus.objects.select_related('machine').all()
    machines = Machine.objects.all()
    shifts = Shift.objects.all()

    # ---------------------
    # Prepare DataFrames
    # ---------------------
    npt_df = pd.DataFrame([{
        "machine_id": npt.machine.id if npt.machine else None,
        "machine_label": f"{npt.machine.mc_no}" if npt.machine else "Unknown",
        "reason": npt.reason.name if npt.reason else "Unknown",
        "off_time": npt.off_time,
        "on_time": npt.on_time
    } for npt in npt_qs])

    rot_df = pd.DataFrame([{
        "machine_id": rot.machine.id if rot.machine else None,
        "machine_label": f"{rot.machine.mc_no}" if rot.machine else "Unknown",
        "count": rot.count,
        "count_time": rot.count_time
    } for rot in rot_qs])

    # Ensure datetime
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

        # NPT duration in hours
        npt_df['npt_hours'] = npt_df.apply(
            lambda row: (row['on_time'] - row['off_time']).total_seconds()/3600
            if row['on_time'] is not pd.NaT else (pd.Timestamp.now() - row['off_time']).total_seconds()/3600,
            axis=1
        )
    else:
        npt_df['shift_name'] = []
        npt_df['npt_hours'] = []

    # ---------------------
    # Metrics
    # ---------------------
    total_npt = npt_df['npt_hours'].sum() if not npt_df.empty else 0
    total_events = len(npt_df)
    machine_count = npt_df['machine_id'].nunique() if not npt_df.empty else 0
    overall_npt_percent = round(total_npt / max(total_npt + 10, 1) * 100, 2)
    overall_pt_percent = 100 - overall_npt_percent
    rolls_produced_total = 55  # example

    # ---------------------
    # Figures
    # ---------------------
    figs = {}
    if not npt_df.empty:
        figs['fig_npt_by_machine'] = px.bar(
            npt_df.groupby(['machine_label'], as_index=False)['npt_hours'].sum(),
            x='machine_label', y='npt_hours', title="NPT by Machine"
        )

        figs['fig_npt_by_reason'] = px.pie(
            npt_df, names='reason', values='npt_hours', title="NPT by Reason"
        )

        figs['fig_npt_by_shift'] = px.bar(
            npt_df.groupby(['machine_label', 'shift_name'], as_index=False)['npt_hours'].sum(),
            x='machine_label', y='npt_hours', color='shift_name',
            barmode='stack', title="Machine NPT by Shift"
        )

        figs['fig_shiftwise_npt'] = px.pie(
            npt_df.groupby(['shift_name'], as_index=False)['npt_hours'].sum(),
            names='shift_name', values='npt_hours', title="Shiftwise NPT Distribution"
        )

        figs['fig_machine_perf'] = px.bar(
            npt_df.groupby(['machine_label'], as_index=False)['npt_hours'].mean(),
            x='machine_label', y='npt_hours', title="Average NPT per Machine"
        )

        figs['fig_shiftwise_trend'] = px.line(
            npt_df.groupby(['shift_name', 'off_time'], as_index=False)['npt_hours'].sum(),
            x='off_time', y='npt_hours', color='shift_name', title="Shiftwise NPT Trend"
        )
    else:
        figs = {k: {} for k in [
            'fig_npt_by_machine', 'fig_npt_by_reason', 'fig_npt_by_shift',
            'fig_shiftwise_npt', 'fig_machine_perf', 'fig_shiftwise_trend'
        ]}

    if not rot_df.empty:
        figs['fig_hourly_trend'] = px.line(
            rot_df, x='count_time', y='count', color='machine_label', title="Hourly Rotation Trend"
        )
    else:
        figs['fig_hourly_trend'] = {}

    # ---------------------
    # Tables
    # ---------------------
    if not npt_df.empty:
        machine_summary = npt_df.groupby(['machine_label']).agg(
            total_npt=('npt_hours', 'sum'),
            events=('machine_label', 'count')
        ).reset_index()
        machine_summary['avg_npt_per_event'] = machine_summary['total_npt'] / machine_summary['events']
        machine_summary['rolls_produced'] = rolls_produced_total
        machine_summary['efficiency'] = (1 - machine_summary['total_npt']/10) * 100
        machine_summary['status'] = machine_summary['efficiency'].apply(lambda x: "Good" if x > 70 else "Warning")
        machine_summary['performance'] = machine_summary['efficiency']

        shift_summary = npt_df.groupby(['shift_name']).agg(
            total_npt=('npt_hours', 'sum'),
            events=('shift_name', 'count')
        ).reset_index()
        shift_summary['avg_npt_per_event'] = shift_summary['total_npt'] / shift_summary['events']
        shift_summary['performance'] = (1 - shift_summary['total_npt']/10) * 100
    else:
        machine_summary = pd.DataFrame()
        shift_summary = pd.DataFrame()

    # Replace DataTable with info_table
    machine_summary_table = info_table(
        machine_summary, title="Machine Performance Summary",
        color="bg-info", icon="fas fa-cogs"
    )

    shift_summary_table = info_table(
        shift_summary, title="Shiftwise NPT Overview",
        color="bg-warning", icon="fas fa-clock"
    )

    return {
        "total_npt": total_npt,
        "total_events": total_events,
        "machine_count": machine_count,
        "overall_npt_percent": overall_npt_percent,
        "overall_pt_percent": overall_pt_percent,
        "rolls_produced_total": rolls_produced_total,
        "figs": figs,
        "tables": {
            "machine_summary_table": machine_summary_table,
            "shift_summary_table": shift_summary_table
        }
    }

# ---------------------
# Layout & Callback
# ---------------------
app.layout = dbc.Container([
    dcc.Interval(id="interval-update", interval=60*1000),  # update every minute
    html.Div(id="dashboard-content")
], fluid=True)

@app.callback(
    Output("dashboard-content", "children"),
    [Input("interval-update", "n_intervals")]
)
def update_dashboard(n):
    data = generate_dashboard_data()
    figs = data["figs"]
    tables = data["tables"]

    total_npt = data["total_npt"]
    hours = int(total_npt)
    minutes = int((total_npt - hours) * 60)
    total_events = data["total_events"]
    machine_count = data["machine_count"]
    overall_npt_percent = data["overall_npt_percent"]
    overall_pt_percent = data["overall_pt_percent"]
    rolls_produced_total = data["rolls_produced_total"]

    return dbc.Container([
        # Cards
        dbc.Row([
            dbc.Col(info_box(f"{hours}h {minutes}m", "Total NPT", "bg-info", "fas fa-clock"), width=2),
            dbc.Col(info_box(total_events, "Total Events", "bg-success", "fas fa-list"), width=2),
            dbc.Col(info_box(machine_count, "Machines", "bg-primary", "fas fa-cogs"), width=2),
            dbc.Col(info_box(f"{overall_npt_percent}%", "Overall NPT %", "bg-warning", "fas fa-chart-pie"), width=2),
            dbc.Col(info_box(f"{overall_pt_percent}%", "Overall PT %", "bg-secondary", "fas fa-percent"), width=2),
            dbc.Col(info_box(rolls_produced_total, "Rolls Produced", "bg-danger", "fas fa-box"), width=2),
        ], className="mb-4"),

        # Charts
        dbc.Row([
            dbc.Col(dcc.Graph(figure=figs["fig_npt_by_machine"], style={"height":"400px"}), width=6),
            dbc.Col(dcc.Graph(figure=figs["fig_npt_by_reason"], style={"height":"400px"}), width=6)
        ], className="mb-4"),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=figs["fig_hourly_trend"], style={"height":"400px"}), width=12)
        ], className="mb-4"),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=figs["fig_npt_by_shift"], style={"height":"400px"}), width=6),
            dbc.Col(dcc.Graph(figure=figs["fig_shiftwise_npt"], style={"height":"400px"}), width=6)
        ], className="mb-4"),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=figs["fig_machine_perf"], style={"height":"400px"}), width=6),
            dbc.Col(dcc.Graph(figure=figs["fig_shiftwise_trend"], style={"height":"400px"}), width=6)
        ], className="mb-4"),

        # Tables
        dbc.Row([
            dbc.Col(tables["machine_summary_table"], width=6),
            dbc.Col(tables["shift_summary_table"], width=6)
        ], className="mb-4")
    ], fluid=True)
