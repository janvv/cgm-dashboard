import dash
import dash_core_components as dcc
import dash_html_components as html

import plotly.graph_objs as go
import numpy as np
from dash.dependencies import Input, Output, State
from datetime import datetime, timedelta
from scipy import interpolate as interp

import agp, cgm
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

cgm_access = cgm.CGMAccess()

colors = {
    'background': '#111111',
    'text': '#FFFFFF'
}

def error_screen():
    return {
        'data': [],
        'layout': go.Layout(
            plot_bgcolor=colors['background'],
            paper_bgcolor=colors['background'],
            font={'color': colors['text']})
    }

def create_agp(df):
    if df is None:
        return error_screen()

    hours, low_10, low_25, median, up_75, up_90 = agp.calculateHourlyStats(df, "date_time", "glucose",
                                                                           smoothed=False, interpolate=True)
    #get last day cgm data
    day_groups = df.groupby("date")
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
    dcc.Interval(id='interval-component', interval=60*1000),
    html.Button(id='load_button', n_clicks=0, children='load'),
])


@app.callback([Output('title', 'children'),Output("agp_graph", "figure")],
              [Input('load_button', 'n_clicks'),Input('interval-component', 'n_intervals')])
def load_callback(n_clicks,n_intervals):
    df = cgm_access.load_last_entries(n=24 * 14 * 12)
    glucose_string = "{:.0f} mg/dl".format(df[df.date == df.date.max()].glucose.values[0])
    return glucose_string, create_agp(df)


if __name__ == '__main__':
    app.run_server(debug=True)