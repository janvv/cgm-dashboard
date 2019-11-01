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

def create_agp(df, datetime_column, glucose_column, date_column):
    if df is None:
        return error_screen()

    hours, low_10, low_25, median, up_75, up_90 = agp.calculateHourlyStats(df, datetime_column, glucose_column,
                                                                           smoothed=False, interpolate=True)

    #get last day cgm data
    day_groups = df.groupby(date_column)
    day_frame = day_groups.get_group(df.date.max()).sort_values("hour", ascending=True)
    H, G = day_frame.hour.values, day_frame.glucose.values

    #smooth and subsample
    G = agp.smooth(G, 5)
    i = np.arange(2, len(G) - 2, 2)
    i = np.append(np.append(0, i), len(G) - 1)
    G, H = G[i], H[i]

    return {
        'data': [
            go.Scatter(x=np.append(hours,np.flip(hours)), y=np.append(low_10, np.flip(up_90)),
                       mode="lines", hoveron='fills', line=dict(width=0),
                       fillcolor="rgba(111, 231, 219,0.5)", fill='toself',
                       text="90th percentile", hoverinfo="text"),

            go.Scatter(x=np.append(hours,np.flip(hours)), y=np.append(low_25, np.flip(up_75)),
                       mode="lines", hoveron='fills', line=dict(width=0),
                       fillcolor="rgba(111, 231, 219,0.5)", fill='toself',
                       text="50th percentile", hoverinfo="text"),

            go.Scatter(x=hours, y=median, mode="lines", line=dict(width=5, color="rgb(111, 231, 219)"),
                       text="median", hoverinfo="text+y"),

            go.Scatter(x=H, y=np.array(G, dtype=int),
                       marker=dict(size=7, color="rgba(127, 166, 238, 0.5)", line=dict(color='rgb(127, 166, 238)', width=1)),
                       #line=dict(width=3, color="rgb(127, 166, 238)"),
                       mode="markers", hoverinfo="y")
        ],
        'layout': go.Layout(
            xaxis=dict(type='linear', title='time of day', zeroline=False, range=[0, 24],
                       ticktext=["2:00","7:00","12:00","17:00","22:00"],
                       tickvals=[2,7,12,17,22], gridcolor='rgb(50,50,50)', showgrid=True),
            yaxis=dict(type='linear', title='glucose', zeroline=False, range=[25, 325],
                       tickvals=[54,70,180,250],
                       ticktext=["54","70","180","250"], gridcolor='rgb(50,50,50)', showgrid=True),
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
    html.Div(id='df_as_json_holder', style={'display': 'none'}, children = ""),
    html.Div(id='last_bgm_json_holder', style={'display': 'none'}, children = ""),

    dcc.Interval(id='load_data_interval', interval=30*1000),
    dcc.Interval(id='refresh_graph_interval', interval=10*1000),
    dcc.Interval(id='refresh_headline_interval', interval=1*1000)

])


@app.callback([Output('df_as_json_holder', 'children'), Output('last_bgm_json_holder', 'children')],
              [Input('load_data_interval','n_intervals'), Input('load_data_button', 'n_clicks')])
def load_data_callback(n_intervals, n_clicks):
    print("reloading data")

    df_as_json = ""
    last_value_as_json = ""
    try:
        cgm_access.update_entries(limit_days=14)
        df = cgm_access.get_entries(14)

        df_as_json = df.to_json()
        last_value = df.loc[df.datetime.idxmax()][["datetime", "glucose"]]
        last_value_as_json = last_value.to_json()
    except Exception as e:
        print(e)
    return [df_as_json, last_value_as_json]


@app.callback([Output("agp_graph", "figure")],
              [Input('refresh_graph_button', 'n_clicks'), Input('refresh_graph_interval', 'n_intervals')],
              [State("df_as_json_holder","children")])
def refresh_graph_callback(n_clicks, n_intervals, df_as_json):
    print("refreshing graph")
    try:
        df = pd.read_json(df_as_json)
    except Exception as e:
        print("error while parsing dataframe: {}".format(e))
        return [error_screen()]
    else:
        return [create_agp(df, datetime_column="datetime", glucose_column="glucose", date_column="date")]


@app.callback([Output('title', 'children')],
              [Input('refresh_graph_button', 'n_clicks'), Input("refresh_headline_interval", "n_intervals")],
              [State("last_bgm_json_holder", "children")])
def refresh_headline_callback(n_clicks, n_intervals, last_value_as_json):

    headline = "???"
    try:
        d = json.loads(last_value_as_json)
        headline = get_headline(datetime.fromtimestamp(d["datetime"]/1000),
                                d["glucose"])
    except Exception as e:
        pass
        #print("error while creating headline: {}".format(e))
    return [headline]




if __name__ == '__main__':
    app.run_server(debug=False)