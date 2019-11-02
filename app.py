import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import numpy as np
import sys
import agp, cgm
import pandas as pd
from datetime import datetime, timedelta
import json
from time import sleep
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css','https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

cgm_access = cgm.CGMAccess()

colors = {
    'background': '#111111',
    'text': '#FFFFFF'
}

dat = ""

def blank_graph(height, id):
    return dcc.Graph(
        id=id,
        figure={
            'data': [],
            'layout': go.Layout(
                plot_bgcolor=colors['background'],
                paper_bgcolor=colors['background'],
                font={'color': colors['text']},
                height= height,
                showlegend=False)})

def agp_graph(cgm_access,show_today=True, show_grid=True):

    graphs = []
    try:
        df = cgm_access.get_entries(14)
        stats = agp.calculateHourlyStats(df,
                                         datetime_column=cgm_access.DATETIME_COLUMN,
                                         glucose_column=cgm_access.GLUCOSE_COLUMN,
                                         smoothed=False, interpolated=True)
        hours, p10, p25, p50, p75, p90 = stats.index.values, stats.glucose.p_10.values, stats.glucose.p_25.values, \
                                         stats.glucose.p_50.values, stats.glucose.p_75.values, stats.glucose.p_90.values
    except Exception as e:
        print("error creating AGP: {}".format(e))
    else:
        graphs = [go.Scatter(x=np.append(hours, np.flip(hours)),
                          y=np.append(p10, np.flip(p90)),
                          mode="lines", hoveron='fills', line=dict(width=0),
                          fillcolor="rgba(111, 231, 219,0.5)", fill='toself',
                          text="90th percentile", hoverinfo="text"),
               go.Scatter(x=np.append(hours, np.flip(hours)),
                          y=np.append(p25, np.flip(p75)),
                          mode="lines", hoveron='fills', line=dict(width=0),
                          fillcolor="rgba(111, 231, 219,0.5)", fill='toself',
                          text="50th percentile", hoverinfo="text"),
               go.Scatter(x=hours,
                          y=p50,
                          mode="lines", line=dict(width=5, color="rgb(111, 231, 219)"),
                          text="median", hoverinfo="text+y")]

    #get last day cgm data
    if show_today:
        df_last_day = cgm_access.get_current_day_entries()
        if df_last_day is not None:
            last_day_graph = [go.Scatter(x=df_last_day[cgm_access.DATETIME_COLUMN].apply(lambda x: x.hour+x.minute/60 + x.second/(3600)).values,
                                          y=np.array(df_last_day[cgm_access.GLUCOSE_COLUMN].values, dtype=int),
                                          marker=dict(size=7, color="rgba(127, 166, 238, 0.5)",
                                          line=dict(color='rgb(127, 166, 238)', width=1)),
                                          mode="markers", hoverinfo="y")]
            graphs = graphs + last_day_graph

    return {
        'data': graphs,
        'layout': go.Layout(
            xaxis=dict(type='linear', zeroline=False, range=[0, 24], #title='time of day',
                       ticktext=["2:00", "7:00", "12:00", "17:00", "22:00"],
                       tickvals=[2, 7, 12, 17, 22], gridcolor='rgb(50,50,50)', showgrid=show_grid),
            yaxis=dict(type='linear', zeroline=False, range=[25, 360], #title='glucose',
                       tickvals=[70, 180, 220],
                       ticktext=["70", "180", "220"], gridcolor='rgb(50,50,50)', showgrid=show_grid),
            margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
            hovermode='closest',
            plot_bgcolor=colors['background'],
            paper_bgcolor=colors['background'],
            showlegend=False,
            font={'color': colors['text']},
            height=450)
    }


def get_headline(t, g):
    dt = (datetime.now() - t)
    headline = "{:.0f} mg/dl ({:02d}:{:02d}:{:02d} ago) "\
        .format(g, int(dt.seconds / 3600), int(np.mod(dt.seconds / 60, 60)), int(np.mod(dt.seconds, 60)))
    return headline



app.layout = html.Div( style={'backgroundColor': colors['background']}, children=[
    html.H1(id="title", children='?? mg/dl', style={'textAlign': 'right',' color': colors['text']}),
    dcc.Graph(id='agp_graph'),
    html.Button(id='load_data_button', n_clicks=0, children='load data'),
    html.Button(id='refresh_graph_button', n_clicks=0, children='refresh graph'),
    html.Div(id='last_loaded_div', children="Last Refresh: ???"),
    dcc.Checklist(id="checkboxes",
                  options=[{'label': 'Today', 'value': 'show_today'},{'label': 'Grid', 'value': 'show_grid'},],
                  value=['show_today'],labelStyle={'display': 'inline-block'}),
    html.Div(
        className="row",
        children=[
            html.Div(
                className="six columns",
                children=[
                    html.Div(
                        children=blank_graph(height=300, id="tir_bars")
                    )
                ]
            ),
            html.Div(
                className="six columns",
                children=html.Div([blank_graph(height=150, id="tir_pie"), blank_graph(height=150, id="pentagon")])
            )
        ]
    ),

    dcc.Interval(id='load_data_interval', interval=10*1000),
    dcc.Interval(id='refresh_headline_interval', interval=1*1000*1000)

])


@app.callback([Output("agp_graph", "figure"), Output("last_loaded_div", "children")],
              [Input('refresh_graph_button', 'n_clicks'),
               Input('load_data_interval', 'n_intervals'),
               Input('checkboxes', 'value')])
             #[State("df_as_json_holder", "children")]
def refresh_agp_graph_callback(n_clicks, n_intervals, checkbox_values):
    cgm_access.update_entries(30)
    last_loaded = "Last Refresh: {}".format(datetime.now().strftime("%H:%M:%S"))

    return [agp_graph(cgm_access,
                         show_today = "show_today" in checkbox_values,
                         show_grid = "show_grid" in checkbox_values),
            last_loaded]


@app.callback([Output('title', 'children')],
              [Input('refresh_graph_button', 'n_clicks'),
               Input("refresh_headline_interval", "n_intervals"),
               Input('load_data_interval', 'n_intervals')])
def refresh_headline_callback(n_clicks, n_intervals, n_interval2):
    headline = "???"
    try:
        latest = cgm_access.get_last_entry()
        headline = get_headline(latest[cgm_access.DATETIME_COLUMN],
                                latest[cgm_access.GLUCOSE_COLUMN])
    except Exception as e:
        print("error while creating headline: {}".format(e))
    return [headline]


@app.callback([Output('tir_bars', 'figure')],
              [Input('load_data_interval', 'n_intervals')])

def refresh_tir_graph(n_intervals):
    print("called")
    labels, means = cgm_access.agg_last_6_months()
    print(means)
    return [{
            'data': [{
                'x': labels,
                'y': means,
                'type': 'bar'}],
            'layout': go.Layout(
                height=300,
                margin={'l': 10, 'b': 20, 't': 0, 'r': 0},
                plot_bgcolor=colors['background'],
                paper_bgcolor=colors['background'],
                showlegend=False,
                font={'color': colors['text']})}]




if __name__ == '__main__':
    app.run_server(debug=True)