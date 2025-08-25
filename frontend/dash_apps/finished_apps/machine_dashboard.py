# frontend/dash_apps/finished_apps/machine_dashboard.py
from dash import html, dcc, dash_table
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from django_plotly_dash import DjangoDash
import pandas as pd
import numpy as np
import plotly.express as px

from library.models import ProcessedNPT, RotationStatus, Shift

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
# Generate Data (function called inside callback)
# ---------------------
def generate_dashboard_data():
    # Fetch data
    npt_qs = ProcessedNPT.objects.all()
    rot_qs = RotationStatus.objects.all()
    shifts = Shift.objects.all()

    npt_df = pd.DataFrame(list(npt_qs.values("mc_no", "reason__name", "off_time", "on_time")))
    rot_df = pd.DataFrame(list(rot_qs.values("mc_no", "count", "count_time")))

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

    npt_df['shift_name'] = npt_df['off_time'].apply(get_shift)

    # ---------------------
    # NPT duration in hours
    # ---------------------
    npt_df['npt_hours'] = npt_df.apply(
        lambda row: (row['on_time'] - row['off_time']).total_seconds()/3600 
        if row['on_time'] else (pd.Timestamp.now() - row['off_time']).total_seconds()/3600,
        axis=1
    )

    # ---------------------
    # Metrics
    # ---------------------
    total_npt = npt_df['npt_hours'].sum()
    total_events = len(npt_df)
    machine_count = npt_df['mc_no'].nunique()
    overall_npt_percent = round(total_npt / (total_npt + 10) * 100, 2)
    overall_pt_percent = 100 - overall_npt_percent
    rolls_produced_total = 55  # example

    # ---------------------
    # Figures
    # ---------------------
    fig_npt_by_machine = px.bar(
        npt_df.groupby(['mc_no'], as_index=False)['npt_hours'].sum(),
        x='mc_no', y='npt_hours', title="NPT by Machine"
    )

    fig_npt_by_reason = px.pie(
        npt_df, names='reason__name', values='npt_hours', title="NPT by Reasons"
    )

    # Fix to_pydatetime FutureWarning
    if not rot_df.empty:
        rot_df['count_time'] = np.array(rot_df['count_time'].dt.to_pydatetime())

    fig_hourly_trend = px.line(
        rot_df, x='count_time', y='count', color='mc_no', title="Hourly NPT Trend (Last 24h)"
    )

    fig_npt_by_shift = px.bar(
        npt_df.groupby(['mc_no', 'shift_name'], as_index=False)['npt_hours'].sum(),
        x='mc_no', y='npt_hours', color='shift_name',
        title="Machine NPT by Shift",
        barmode='stack'
    )

    fig_shiftwise_npt = px.pie(
        npt_df.groupby(['shift_name'], as_index=False)['npt_hours'].sum(),
        names='shift_name', values='npt_hours',
        title="Shiftwise NPT Distribution"
    )

    fig_machine_perf = px.bar(
        npt_df.groupby(['mc_no'], as_index=False)['npt_hours'].mean(),
        x='mc_no', y='npt_hours',
        title="Average NPT per Machine"
    )

    fig_shiftwise_trend = px.line(
        npt_df.groupby(['shift_name', 'off_time'], as_index=False)['npt_hours'].sum(),
        x='off_time', y='npt_hours', color='shift_name',
        title="Shiftwise NPT Overview"
    )

    # ---------------------
    # Tables
    # ---------------------
    machine_summary = npt_df.groupby(['mc_no']).agg(
        total_npt=('npt_hours', 'sum'),
        events=('mc_no', 'count')
    ).reset_index()
    machine_summary['avg_npt_per_event'] = machine_summary['total_npt'] / machine_summary['events']
    machine_summary['rolls_produced'] = rolls_produced_total
    machine_summary['efficiency'] = (1 - machine_summary['total_npt']/10) * 100
    machine_summary['status'] = machine_summary['efficiency'].apply(lambda x: "Good" if x > 70 else "Warning")
    machine_summary['performance'] = machine_summary['efficiency']

    machine_summary_table = dash_table.DataTable(
        columns=[{"name": i.replace('_',' ').title(), "id": i} for i in machine_summary.columns],
        data=machine_summary.to_dict('records'),
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'center', 'padding': '5px'},
        style_header={'backgroundColor': '#f8f9fa', 'fontWeight': 'bold'}
    )

    shift_summary = npt_df.groupby(['shift_name']).agg(
        total_npt=('npt_hours', 'sum'),
        events=('shift_name', 'count')
    ).reset_index()
    shift_summary['avg_npt_per_event'] = shift_summary['total_npt'] / shift_summary['events']
    shift_summary['performance'] = (1 - shift_summary['total_npt']/10) * 100

    shift_summary_table = dash_table.DataTable(
        columns=[{"name": i.replace('_',' ').title(), "id": i} for i in shift_summary.columns],
        data=shift_summary.to_dict('records'),
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'center', 'padding': '5px'},
        style_header={'backgroundColor': '#f8f9fa', 'fontWeight': 'bold'}
    )

    return {
        "total_npt": total_npt,
        "total_events": total_events,
        "machine_count": machine_count,
        "overall_npt_percent": overall_npt_percent,
        "overall_pt_percent": overall_pt_percent,
        "rolls_produced_total": rolls_produced_total,
        "figs": {
            "fig_npt_by_machine": fig_npt_by_machine,
            "fig_npt_by_reason": fig_npt_by_reason,
            "fig_hourly_trend": fig_hourly_trend,
            "fig_npt_by_shift": fig_npt_by_shift,
            "fig_shiftwise_npt": fig_shiftwise_npt,
            "fig_machine_perf": fig_machine_perf,
            "fig_shiftwise_trend": fig_shiftwise_trend
        },
        "tables": {
            "machine_summary_table": machine_summary_table,
            "shift_summary_table": shift_summary_table
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
def update_dashboard(n):
    data = generate_dashboard_data()
    figs = data["figs"]
    tables = data["tables"]

    total_npt = data["total_npt"]
    total_events = data["total_events"]
    machine_count = data["machine_count"]
    overall_npt_percent = data["overall_npt_percent"]
    overall_pt_percent = data["overall_pt_percent"]
    rolls_produced_total = data["rolls_produced_total"]

    return dbc.Container([
        # Cards
        dbc.Row([
            dbc.Col(info_box(f"{int(total_npt)}h {int(total_npt % 1*60)}m", "Total NPT", "bg-info", "fas fa-clock", ''), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Total Events"), html.H2(total_events)])), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Machines"), html.H2(machine_count)])), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Overall NPT %"), html.H2(f"{overall_npt_percent}%")])), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Overall PT %"), html.H2(f"{overall_pt_percent}%")])), width=2),
            dbc.Col(dbc.Card(dbc.CardBody([html.H5("Rolls Produced"), html.H2(rolls_produced_total)])), width=2),
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
            dbc.Col([
                html.H5("Machine Performance Summary"),
                tables["machine_summary_table"]
            ], width=6),
            dbc.Col([
                html.H5("Shiftwise NPT Overview"),
                tables["shift_summary_table"]
            ], width=6)
        ], className="mb-4")
    ], fluid=True)
