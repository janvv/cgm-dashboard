import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import numpy as np
import sys
import agp, cgm
from datetime import datetime, time

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css',
                        'https://codepen.io/chriddyp/pen/bWLwgP.css']

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

def blank_graph(id, height):
    return dcc.Graph(
        style={"height":height},
        id=id,
        figure={
            'data': [],
            'layout': go.Layout(
                plot_bgcolor=colors['background'],
                paper_bgcolor=colors['background'],
                font={'color': colors['text']},
                showlegend=False)},
        config={
            'displayModeBar': False
        })

def fill_above(X, Ylow, Ytop, thresh_bottom, thresh_top):
    bottom1 = np.array([max(thresh_top, y) for y in Ylow])
    top1 = np.array([max(thresh_top, y) for y in Ytop])

    fill_top = go.Scatter(x=np.append(X, np.flip(X)),
                          y=np.append(bottom1, np.flip(top1)),
                          mode="lines", hoveron='fills', line=dict(width=0),
                          fillcolor=colors["signal"], fill='toself',
                          text="50th percentile", hoverinfo="text",
                          showlegend=False)

    top2 = np.array([min(thresh_bottom, y) for y in Ytop])
    bottom2 = np.array([min(thresh_bottom, y) for y in Ylow])
    fill_bottom = go.Scatter(x=np.append(X, np.flip(X)),
                          y=np.append(bottom2, np.flip(top2)),
                          mode="lines", hoveron='fills', line=dict(width=0),
                          fillcolor=colors["signal"], fill='toself',
                          text="50th percentile", hoverinfo="text",
                          showlegend=False)
    return [fill_top,fill_bottom]


def shift(x, shift):
    temp = (x+shift) % 24
    return temp, np.argsort(temp)


def agp_components(df, start=0):
    stats = agp.calculateHourlyStats(df, datetime_column=cgm_access.DATETIME_COLUMN,
                                     glucose_column=cgm_access.GLUCOSE_COLUMN,
                                     smoothed=False, interpolated=True)

    index_copy = stats.index.values
    index_copy[index_copy < start] += 24
    stats.index = index_copy
    stats.sort_index(inplace=True)

    hours, p10, p25, p50, p75, p90 = stats.index.values, stats.glucose.p_10.values, stats.glucose.p_25.values, \
                                     stats.glucose.p_50.values, stats.glucose.p_75.values, stats.glucose.p_90.values

    graphs = [go.Scatter(x=np.append(hours, np.flip(hours)),
                         y=np.append(p10, np.flip(p90)),
                         mode="lines", hoveron='fills', line=dict(width=0),
                         fillcolor=colors["third"], fill='toself',
                         text="90th percentile", hoverinfo="text",
                         showlegend=False, ),
              go.Scatter(x=np.append(hours, np.flip(hours)),
                         y=np.append(p25, np.flip(p75)),
                         mode="lines", hoveron='fills', line=dict(width=0),
                         fillcolor=colors["second"], fill='toself',
                         text="50th percentile", hoverinfo="text",
                         showlegend=False)]
    graphs += fill_above(hours, p25, p75, 70, 180)
    graphs += [go.Scatter(x=hours, y=p50, mode="lines", line=dict(width=5, color=colors["first"]),
                          text="median", hoverinfo="y", hovertemplate='<br>%{y:3.0f} mg/dl', showlegend=False)]
    return graphs

def major_formatter(x):
    if x == 24:
        d = time(hour=23, minute=59, second=59)
    else:
        d = time(hour=np.mod(int(x), 24), minute=int(60*(x-int(x))))
    return d.strftime('%H:%M')


def top_graph(cgm_access,n=14, show_today=True, show_grid=True, centered=False):
    ylim = 275

    start = 0
    end = 24
    ticks = [0,4,8,12,16,20]
    if centered:
        now = datetime.now()
        now_hour = now.hour + now.minute / 60
        preview = 6
        start = (now_hour + preview) % 24 if centered else 0
        end = start + 24
        ticks = np.append(ticks, now.hour+now.minute/60)
        ticks[ticks < start] += 24


    graphs = []
    try:
        df = cgm_access.get_entries(n)
        graphs = graphs + agp_components(df, start)
    except Exception as e:
        print("error creating AGP: {}".format(e))


    #get last day cgm data
    if show_today:
        try:
            df_last_day = cgm_access.get_current_day_entries()
        except Exception as e:
            print("Error while adding day scatter plot: {}".format(e))
        else:
            if df_last_day is not None:
                hours = df_last_day[cgm_access.DATETIME_COLUMN].apply(lambda x: x.hour + x.minute/60 + x.second/3600).values
                strings = df_last_day[cgm_access.DATETIME_COLUMN].apply(lambda x: x.strftime("%H:%M")).values
                last_day_graph = [go.Scatter(x=hours,
                                             y=np.array(df_last_day[cgm_access.GLUCOSE_COLUMN].values, dtype=int),
                                             marker=dict(size=7, color=colors["bright"], line=dict(color="white", width=1)),
                                             text=strings,
                                             mode="markers", hoverinfo="y+text",  hovertemplate = '%{y:3.0f} mg/dl <br> %{text}',
                                             showlegend=False)]
                graphs = graphs + last_day_graph
    return {
        'data': graphs,
        'layout': go.Layout(
            xaxis=dict(type='linear', zeroline=False, range=[start, end],
                       ticktext=[major_formatter(x) for x in ticks], fixedrange=True,
                       tickvals=ticks, gridcolor=colors["text"], showgrid=show_grid),
            yaxis=dict(type='linear', zeroline=False, range=[25, ylim], #title='glucose',
                       tickvals=[70, 180, 220], fixedrange=True,
                       ticktext=["70", "180", "220"], gridcolor=colors["text"], showgrid=show_grid),
            margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
            hovermode='closest',
            plot_bgcolor=colors['background'],
            paper_bgcolor=colors['background'],
            showlegend=False,
            font={'color': colors['text']})
    }


def get_headline():

    latest = cgm_access.get_last_entry()
    if latest is not None:
        minutes = (datetime.now() - latest[cgm_access.DATETIME_COLUMN]).seconds/60
        #t_div = html.Div("mg/dl ({} min ago)".format(int(minutes)), style={'marginLeft':8, 'marginRight':12, 'display': 'inline-block', "font-size": 24})
        children = [html.Div("{:.0f}".format(latest[cgm_access.GLUCOSE_COLUMN]),
                             style={'display': 'inline-block', "font-size": 56}),
                    html.Div("mg/dl".format(latest[cgm_access.GLUCOSE_COLUMN]),
                             style={'marginLeft': 8, 'marginRight': 16, 'display': 'inline-block', "font-size": 24})]
        if minutes < 15:
            return html.Div(children=children, style={'textAlign': 'right'})
        else:
            return html.Del(children=children, style={'textAlign': 'right'})
    else:
        return html.Div("???", style={'textAlign': 'right'})


app.layout = html.Div(style={"height": "100vh", "width": "100vw", 'backgroundColor': colors['background'], 'color': colors['text']}, children=[
    html.Div(className="row", children=[
        html.Div(className="six columns", style={'display': 'inline-block'}, children=[
            html.Div(id='last_loaded_div', children="Last Refresh: ???", style={'width': '200px', 'display': 'inline-block', 'text-align': 'center'}),
            dcc.Checklist(id="checkboxes",
                          options=[{'label': 'Today', 'value': 'show_today'},
                                   {'label': 'Center', 'value': 'centered'},
                                   {'label': 'Grid', 'value': 'show_grid'}],
                          value=['show_today', "show_grid"],
                          labelStyle={'display': 'inline-block'},
                          style={'display': 'inline-block'}),
            html.Div(dcc.Slider(id="day_slider", min=1, max=5, step=1, value=2,
                                marks=dict(zip([1, 2, 3, 4, 5], ["7d", "14d", "30d", "90d", "365d"]))),
                     style={"width": 200, "marginLeft": 20, 'display': 'inline-block'})
        ]),
        html.Div(className="six columns", id="title")
    ]),
    html.Div(children=[blank_graph(id='top_graph', height="70vh")]),

    html.Div(
        style={"height": "20vh"},
        className="row",
        children=[
            html.Div(className="twelve columns", children=blank_graph(id="tir_bars",height="20vh"))]),
            #html.Div(className="six columns", children=html.Div([blank_graph(id="pentagon", height=150)]))]),

    dcc.Interval(id='update_tir_interval', interval=30*60*1000),
    dcc.Interval(id='update_agp_interval', interval=1*60*1000),
    dcc.Interval(id='startup_interval', interval=1*1000, max_intervals=1)
    ])

@app.callback([Output("top_graph", "figure"),
               Output("last_loaded_div", "children"),
               Output('title', 'children')],
              [Input('update_agp_interval', 'n_intervals'),
               Input("startup_interval", "n_intervals"),
               Input('checkboxes', 'value'),
               Input('day_slider', 'value')])
def refresh_agp_graph_callback(n_interval_load, n_startup_interval, checkbox_values, slider_value):
    num_days = [7, 14, 30, 90, 365][slider_value-1]
    last_loaded = "last refresh {}".format(datetime.now().strftime("%H:%M:%S"))
    return [top_graph(cgm_access, n=num_days,
                      show_today="show_today" in checkbox_values,
                      show_grid="show_grid" in checkbox_values,
                      centered="centered" in checkbox_values),
            last_loaded,
            get_headline()]

@app.callback([Output('tir_bars', 'figure')],
              [Input('update_tir_interval', 'n_intervals'),
               Input("startup_interval","n_intervals")])
def refresh_tir_graph(n_intervals,n_startup_interval):
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
             'layout': go.Layout(yaxis=dict(fixedrange=True),
                                 xaxis=dict(fixedrange=True),
                                 barmode='stack', margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
                                 plot_bgcolor=colors['background'],
                                 paper_bgcolor=colors['background'],
                                 showlegend=False,

                                 font={'color': colors['text']})}]



if __name__ == '__main__':
    debug = False
    if "-debug" in sys.argv:
        print("starting in debug")
        debug = True
    app.run_server(debug=debug, port=8080, host='0.0.0.0')
