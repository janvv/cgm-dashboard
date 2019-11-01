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
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

cgm_access = cgm.CGMAccess()

colors = {
    'background': '#111111',
    'text': '#FFFFFF'
}

dat = ""

def error_screen():
    return {
        'data': [],
        'layout': go.Layout(
            plot_bgcolor=colors['background'],
            paper_bgcolor=colors['background'],
            font={'color': colors['text']})
    }

def create_graph(cgm_access):

    agp_graphs =[]
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
        agp_graphs = [go.Scatter(x=np.append(hours, np.flip(hours)),
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
    last_day_graphs = []
    df_last_day = cgm_access.get_current_day_entries()
    if df_last_day is not None:
        last_day_graphs = [go.Scatter(x=df_last_day[cgm_access.DATETIME_COLUMN].apply(lambda x: x.hour+x.minute/60 + x.second/(3600)).values,
                                      y=np.array(df_last_day[cgm_access.GLUCOSE_COLUMN].values, dtype=int),
                                      marker=dict(size=7, color="rgba(127, 166, 238, 0.5)",
                                      line=dict(color='rgb(127, 166, 238)', width=1)),
                                      mode="markers", hoverinfo="y")]

    return {
        'data': agp_graphs + last_day_graphs,
        'layout': go.Layout(
            xaxis=dict(type='linear', title='time of day', zeroline=False, range=[0, 24],
                       ticktext=["2:00", "7:00", "12:00", "17:00", "22:00"],
                       tickvals=[2, 7, 12, 17, 22], gridcolor='rgb(50,50,50)', showgrid=True),
            yaxis=dict(type='linear', title='glucose', zeroline=False, range=[25, 325],
                       tickvals=[54, 70, 180, 250],
                       ticktext=["54", "70", "180", "250"], gridcolor='rgb(50,50,50)', showgrid=True),
            margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
            #legend={'x': 0, 'y': 1},
            hovermode='closest',
            plot_bgcolor=colors['background'],
            paper_bgcolor=colors['background'],
            showlegend=False,
            font={'color': colors['text']}
        )
    }


def get_headline(t, g):
    dt = (datetime.now() - t)
    headline = "{:.0f} mg/dl ({:02d}:{:02d}:{:02d} ago) "\
        .format(g, int(dt.seconds / 3600), int(np.mod(dt.seconds / 60, 60)), int(np.mod(dt.seconds, 60)))
    return headline


app.layout = html.Div( style={'backgroundColor': colors['background']}, children=[
    html.H1(
        id = "title",
        children='?? mg/dl',
        style={
            'textAlign': 'right','color': colors['text']
        }
    ),
    #html.Div(id='current_glucose', style={'color': colors['text'], "font-size":"36px", "textAlign":"right"}),
    dcc.Graph(id='agp_graph'),
    html.Button(id='load_data_button', n_clicks=0, children='load data'),
    html.Button(id='refresh_graph_button', n_clicks=0, children='refresh graph'),

    # Hidden div inside the app that stores the intermediate value
    #html.Div(id='df_as_json_holder', style={'display': 'none'}, children = ""),
    html.Div(id='last_loaded_div', children = "Last Refresh: ???"),#style={'display': 'none'},

    dcc.Interval(id='load_data_interval', interval=10*1000),
    dcc.Interval(id='refresh_headline_interval', interval=1*1000)

])


@app.callback([Output("agp_graph", "figure"),Output("last_loaded_div", "children")],
              [Input('refresh_graph_button', 'n_clicks'), Input('load_data_interval', 'n_intervals')])
             #[State("df_as_json_holder", "children")]
def refresh_graph_callback(n_clicks, n_intervals):
    cgm_access.update_entries(30)
    last_loaded = "Last Refresh: {}".format(datetime.now().strftime("%H:%M:%S"))
    return [create_graph(cgm_access), last_loaded]


@app.callback([Output('title', 'children')],
              [Input('refresh_graph_button', 'n_clicks'),
               Input("refresh_headline_interval", "n_intervals"),
               Input('load_data_interval', 'n_intervals')])
def refresh_headline_callback(n_clicks, n_intervals,n_interval2):
    headline = "???"
    try:
        latest = cgm_access.get_last_entry()
        headline = get_headline(latest[cgm_access.DATETIME_COLUMN],
                                latest[cgm_access.GLUCOSE_COLUMN])
    except Exception as e:
        print("error while creating headline: {}".format(e))
    return [headline]




if __name__ == '__main__':
    app.run_server(debug=True)