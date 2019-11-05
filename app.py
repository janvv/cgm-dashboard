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
    'text': '#ffffff',
    'bright': "rgba(243, 255, 189, 0.75)",
    'first': "rgba(178,219, 191, 0.75)",
    'second': "rgba(112, 193, 179,0.75)",
    'third': "rgba(36,123,160,0.75)",
    'signal': "rgba(255,22,84,0.75)"}

def blank_graph(id,height):
    return dcc.Graph(
        id=id,
        figure={
            'data': [],
            'layout': go.Layout(
                plot_bgcolor=colors['background'],
                paper_bgcolor=colors['background'],
                font={'color': colors['text']},
                showlegend=False,
                height=height)})

def agp_graph(cgm_access,n=14, show_today=True, show_grid=True):

    ylim = 275
    graphs = []
    try:
        df = cgm_access.get_entries(n)
        stats = agp.calculateHourlyStats(df,
                                         datetime_column=cgm_access.DATETIME_COLUMN,
                                         glucose_column=cgm_access.GLUCOSE_COLUMN,
                                         smoothed=False, interpolated=True)
        hours, p10, p25, p50, p75, p90 = stats.index.values, stats.glucose.p_10.values, stats.glucose.p_25.values, \
                                         stats.glucose.p_50.values, stats.glucose.p_75.values, stats.glucose.p_90.values
        ylim = max(ylim, max(p90))
    except Exception as e:
        print("error creating AGP: {}".format(e))
    else:
        graphs = [go.Scatter(x=np.append(hours, np.flip(hours)),
                          y=np.append(p10, np.flip(p90)),
                          mode="lines", hoveron='fills', line=dict(width=0),
                          fillcolor=colors["third"], fill='toself',
                          text="90th percentile", hoverinfo="text"),
               go.Scatter(x=np.append(hours, np.flip(hours)),
                          y=np.append(p25, np.flip(p75)),
                          mode="lines", hoveron='fills', line=dict(width=0),
                          fillcolor=colors["second"], fill='toself',
                          text="50th percentile", hoverinfo="text"),
               go.Scatter(x=hours,
                          y=p50,
                          mode="lines", line=dict(width=5, color=colors["first"]),
                          text="median", hoverinfo="y", hovertemplate = '<br>%{y:3.0f} mg/dl')]

    #get last day cgm data
    if show_today:
        try:
            df_last_day = cgm_access.get_current_day_entries()
        except Exception as e:
            print("Error while adding day scatter plot: {}".format(e))
        else:
            if df_last_day is not None:
                ylim = max(ylim, df_last_day[cgm_access.GLUCOSE_COLUMN].max())
                last_day_graph = [go.Scatter(x=df_last_day[cgm_access.DATETIME_COLUMN].apply(lambda x: x.hour+x.minute/60 + x.second/(3600)).values,
                                              y=np.array(df_last_day[cgm_access.GLUCOSE_COLUMN].values, dtype=int),
                                              marker=dict(size=7, color=colors["bright"],
                                              line=dict(color="white", width=1)),
                                              mode="markers", hoverinfo="y",  hovertemplate = '%{y:3.0f} mg/dl')]
                graphs = graphs + last_day_graph
    return {
        'data': graphs,
        'layout': go.Layout(
            xaxis=dict(type='linear', zeroline=False, range=[0, 24], #title='time of day',
                       ticktext=["2:00", "7:00", "12:00", "17:00", "22:00"],
                       tickvals=[2, 7, 12, 17, 22], gridcolor=colors["text"], showgrid=show_grid),
            yaxis=dict(type='linear', zeroline=False, range=[25,ylim], #title='glucose',
                       tickvals=[70, 180, 220],
                       ticktext=["70", "180", "220"], gridcolor=colors["text"], showgrid=show_grid),
            margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
            hovermode='closest',
            plot_bgcolor=colors['background'],
            paper_bgcolor=colors['background'],
            showlegend=False,
            font={'color': colors['text']})
    }


def get_headline(t, g):
    dt = (datetime.now() - t)
    headline = "{:.0f} mg/dl ({:02d}:{:02d}:{:02d} ago) "\
        .format(g, int(dt.seconds / 3600), int(np.mod(dt.seconds / 60, 60)), int(np.mod(dt.seconds, 60)))
    return headline


app.layout = html.Div(style={'backgroundColor': colors['background'], 'color': colors['text']}, children=[
    html.Div([
        html.Div(style={'width': '49%', 'display': 'inline-block'}, children=[
            html.Div(id='last_loaded_div', children="Last Refresh: ???", style={'width': '200px', 'display': 'inline-block', 'text-align': 'center'}),
            dcc.Checklist(id="checkboxes",
                          options=[{'label': 'Today', 'value': 'show_today'},
                                   {'label': 'Grid', 'value': 'show_grid'}],
                          value=['show_today'],
                          labelStyle={'display': 'inline-block'},
                          style={'display': 'inline-block'}),
            html.Div(dcc.Slider(id="day_slider", min=1, max=5, step=1, value=2,
                                marks=dict(zip([1, 2, 3, 4, 5], ["7d", "14d", "30d", "90d", "365d"]))),
                     style={"width": 200, "marginLeft": 20, 'display': 'inline-block'})
        ]),
        html.Div(style={'width':'49%', 'display': 'inline-block'}, children=[
            html.H1(id="title", children='?? mg/dl', style={'textAlign': 'right', 'color': colors['text']})])]),
    html.Div([blank_graph(id='agp_graph',height=None)]),

    html.Div(
        className="row",
        children=[
            html.Div(className="six columns", children=blank_graph(id="tir_bars", height=150)),
            html.Div(className="six columns", children=html.Div([blank_graph(id="pentagon", height=150)]))]),

    dcc.Interval(id='update_tir_interval', interval=30*60*1000),
    dcc.Interval(id='update_agp_interval', interval=10*1000),
    dcc.Interval(id='update_headline_interval', interval=1*1000),
    dcc.Interval(id='startup_interval', interval=1*1000,max_intervals=1)

])


@app.callback([Output("agp_graph", "figure"), Output("last_loaded_div", "children")],
              [Input('update_agp_interval', 'n_intervals'),Input("startup_interval","n_intervals"),
               Input('checkboxes', 'value'),
               Input('day_slider', 'value')])
def refresh_agp_graph_callback(n_interval_load, n_startup_interval, checkbox_values, slider_value):
    num_days = [7, 14, 30, 90, 365][slider_value-1]
    last_loaded = "Last Refresh: {}".format(datetime.now().strftime("%H:%M:%S"))
    return [agp_graph(cgm_access, n=num_days, show_today="show_today" in checkbox_values, show_grid="show_grid" in checkbox_values),
            last_loaded]


@app.callback([Output('title', 'children')],
              [Input("update_headline_interval", "n_intervals"),
               Input('update_agp_interval', 'n_intervals')])
def refresh_headline_callback(n_interval_headline, n_interval_load):
    headline = "???"
    latest = cgm_access.get_last_entry()
    if latest is not None:
        headline = get_headline(latest[cgm_access.DATETIME_COLUMN],latest[cgm_access.GLUCOSE_COLUMN])
    return [headline]


@app.callback([Output('tir_bars', 'figure')],
              [Input('update_tir_interval', 'n_intervals'), Input("startup_interval","n_intervals")])
def refresh_tir_graph(n_intervals,n_startup_interval):
    print("update tir")
    result = cgm_access.agg_last_6_months()

    if result is None:
        return [{'data': [{'x': [], 'y': [], 'type': 'bar'}],
                 'layout': go.Layout(margin={'l': 40, 'b': 40, 't': 10, 'r': 10})}]

    hypos = np.array([r[0] for r in result[1]])
    range = np.array([r[1] for r in result[1]])
    hyprs = np.array([r[2] for r in result[1]])
    return [{'data': [go.Bar(x=result[0], y=hypos, name='hypos', marker=go.bar.Marker(color=colors["signal"]), hoverinfo="y+x", hovertemplate= '%{y:3.1%}'),
                      go.Bar(x=result[0], y=range, name='in range', marker=go.bar.Marker(color=colors["second"]),hoverinfo="y+x", hovertemplate= '%{y:3.1%}'),
                      go.Bar(x=result[0], y=hyprs, name='hypers', marker=go.bar.Marker(color=colors["bright"]),hoverinfo="y+x", hovertemplate= '%{y:3.1%}')],
             'layout': go.Layout(yaxis=dict(range=[0, 1]), barmode='stack', margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
                                 plot_bgcolor=colors['background'], paper_bgcolor=colors['background'], showlegend=False,
                                 font={'color': colors['text']})}]



if __name__ == '__main__':
    app.run_server(debug=True, port=8080, host='0.0.0.0')