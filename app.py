import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go

import numpy as np
import sys
import cgm
from configparser import ConfigParser
import logging

from adapter import MongoAdapter, MongoAdapterSRV, RestAdapter, OfflineAdapter
from database import DataBase, DATETIME_COLUMN, GLUCOSE_COLUMN
from datetime import datetime, time, timedelta


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css',
                        'https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

#create root logger

fmt='%(asctime)s|%(name)s|%(funcName)s|%(levelname)s: %(message)s'
datefmt='%m/%d/%Y %I:%M:%S %p'
log_level = logging.WARNING

logging.basicConfig(format=fmt, datefmt=datefmt, level=log_level)
formatter = logging.Formatter(fmt, datefmt)

#add file handler
fh = logging.FileHandler("log.log",mode="w",encoding="utf-8")
fh.setLevel(log_level)
fh.setFormatter(formatter)
rootLogger = logging.getLogger()
rootLogger.addHandler(fh)

logger = logging.getLogger("app")


#setup database and backend adapter
config = ConfigParser()
config.read('config.ini')
section = config.sections()[0]
if section == "MongoDB":
    logger.info("Connecting to MongoDB")
    adapter = MongoAdapter(config["MongoDB"])
if section == "MongoDB+SRV":
    logger.info("Connecting to MongoDB+SRV")
    adapter = MongoAdapterSRV(config[section])
elif section == "REST":
    logger.info("Connecting to REST")
    adapter = RestAdapter(config["REST"])
elif section == "OFFLINE":
    adapter = OfflineAdapter()
else:
    logger.error("config named {} does not exist, exiting ...".format(section))
    exit()

database = DataBase(adapter)



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
        style={"height": height},
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
    return [fill_top, fill_bottom]


def agp_components(df, start=0):
    stats = cgm.calculate_hourly_stats(df, datetime_column=DATETIME_COLUMN, glucose_column=GLUCOSE_COLUMN,
                                       interpolated=True)

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
        d = time(hour=np.mod(int(x), 24), minute=int(60 * (x - int(x))))
    return d.strftime('%H:%M')


def scatter_graph(df, start=0, hover=True, mode='markers', size=7, color=None, edge=False):
    df = df.copy()
    df["hour"] = df[DATETIME_COLUMN].apply(lambda x: x.hour + x.minute / 60 + x.second / 3600)
    df["glucose_smoothed"] = cgm.smooth_split(df[GLUCOSE_COLUMN].values, df[DATETIME_COLUMN].values, order=6)
    # moves hours of current day in front of hours of previous day
    df.loc[df.hour < start, "hour"] = df[df.hour < start].hour + 24

    scatter = go.Scatter(x=df.hour,
                         y=df.glucose_smoothed,
                         text=df[DATETIME_COLUMN].apply(lambda x: x.strftime("%H:%M")).values[:-1],
                         marker=dict(size=size,
                                     color="#808080" if color is None else color,
                                     line=dict(color="white", width=3) if edge else None),
                         mode=mode,
                         hoverinfo="y+text" if hover else 'none',
                         hovertemplate='%{y:3.0f} mg/dl <br> %{text}' if hover else '',
                         showlegend=False)
    return scatter


def top_graph(df, show_today=True, show_days=True, show_grid=True, centered=False):
    ylim = 270
    start = 0
    end = 24
    ticks = np.array([0, 4, 8, 12, 16, 20])
    preview = 0

    if centered:
        preview = 6
        now = datetime.now()
        now_hour = now.hour + now.minute / 60
        start = (now_hour + preview) % 24
        end = start + 24

        # remove close grid lines

        ticks[ticks < start] += 24
        now_tick = now_hour if now_hour >= start else now_hour + 24

        ticks = ticks[~(np.abs(now_tick - ticks) <= 1.5)]
        ticks = np.append(ticks, now_tick)

    graphs = []
    annotations = []

    # draw AGP
    try:
        graphs = graphs + agp_components(df, start)
    except Exception as e:
        logger.error("error creating AGP: {}".format(e))

    # get previous days
    day_groups = df.groupby(df[DATETIME_COLUMN].apply(lambda x: x.date()))
    today_date = datetime.today().date()
    day_dates = day_groups.keys.unique()
    previous_dates = [date for date in day_dates if date != today_date]

    # draw previous day scatters
    if show_days:
        for date in previous_dates:
            subframe = day_groups.get_group(date)
            scatter = scatter_graph(subframe, start, hover=False, size=4)
            graphs = graphs + [scatter]

    if show_today:
        # prevent warping
        today_start = datetime(today_date.year, today_date.month, today_date.day)
        cut_off = datetime.now() - timedelta(hours=24.0 - preview) if centered else today_start
        df_recent = df.loc[df[DATETIME_COLUMN] > cut_off]

        # if values in current view exist
        if len(df_recent) > 0:
            graphs = graphs + [scatter_graph(df_recent, start, hover=True, size=7, edge=True, color=colors["bright"])]
            # make last value bigger if up to date
            if (datetime.now() - df[DATETIME_COLUMN].iloc[-1]) < timedelta(minutes=15):
                glucose = df[GLUCOSE_COLUMN].iloc[-1]
                color = colors["signal"] if (glucose < 54) else (
                    colors["second"] if (glucose < 220) else colors["third"])
                graphs = graphs + [scatter_graph(df.iloc[[-1]], start, hover=True, size=20, edge=True, color=color)]

    return {
        'data': graphs,
        'layout': go.Layout(
            xaxis=dict(type='linear', zeroline=False, range=[start, end],
                       ticktext=[major_formatter(x) for x in ticks], fixedrange=True,
                       tickvals=ticks, gridcolor='#808080', showgrid=show_grid),
            yaxis=dict(type='linear', zeroline=False, range=[40, ylim],  # title='glucose',
                       tickvals=[70, 180, 220], fixedrange=True,
                       ticktext=["70", "180", "220"], gridcolor='#808080', showgrid=show_grid),
            margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
            hovermode='closest',
            plot_bgcolor=colors['background'],
            paper_bgcolor=colors['background'],
            showlegend=False,
            annotations=annotations,
            font={'color': colors['text']})
    }


def get_headline(latest):
    if latest is not None:
        minutes = (datetime.now() - latest[DATETIME_COLUMN]).seconds / 60

        container = html.Div if minutes < 15 else html.Del
        color = colors["text"] if minutes < 15 else "#808080"
        return html.Div(children=[container(" {:.0f} ".format(latest[GLUCOSE_COLUMN]),
                                            style={'display': 'inline-block', "font-size": 64, 'color': color}),
                                  html.Div("mg/dl".format(latest[GLUCOSE_COLUMN]),
                                           style={'marginLeft': 8, 'marginRight': 16, 'display': 'inline-block',
                                                  "font-size": 24, 'color': color})],
                        style={'textAlign': 'right'})
    else:
        return html.Div("???")


app.layout = html.Div(style={"height": "100vh", "width": "100vw", 'backgroundColor': colors['background'],
                             'color': colors['text']}, children=[

    html.Div(id="title", style={'textAlign': 'right', 'height': '15vh'}),

    html.Div(children=[blank_graph(id='top_graph', height="85vh")]),

    html.Div(style={'display': 'inline-block', 'height': '10vh'}, children=[
        html.Div(id='last_loaded_div', children="Last Refresh: ???",
                 style={'width': '200px', 'display': 'inline-block', 'text-align': 'center'}),
        dcc.Checklist(id="checkboxes",
                      options=[{'label': 'Today', 'value': 'show_today'},
                               {'label': 'Days', 'value': 'show_days'},
                               {'label': 'Center', 'value': 'is_centered'},
                               {'label': 'Grid', 'value': 'show_grid'}],
                      value=['show_today', 'is_centered', 'show_grid'],
                      labelStyle={'display': 'inline-block'},
                      style={'display': 'inline-block'}),
        html.Div(dcc.Slider(id="day_slider", min=1, max=5, step=1, value=2,
                            marks=dict(zip([1, 2, 3, 4, 5], ["7d", "14d", "30d", "90d", "365d"]))),
                 style={"width": 200, "marginLeft": 20, 'display': 'inline-block'})]),


    # blank_graph(id="tir_bars", height="20vh"),
    dcc.Interval(id='update_tir_interval', interval=30 * 60 * 1000),
    dcc.Interval(id='update_agp_interval', interval=1 * 60 * 1000),
    dcc.Interval(id='startup_interval', interval=1 * 1000, max_intervals=1)
])


@app.callback([Output("top_graph", "figure"),
               Output("last_loaded_div", "children"),
               Output('title', 'children')],
              [Input('update_agp_interval', 'n_intervals'),
               Input("startup_interval", "n_intervals"),
               Input('checkboxes', 'value'),
               Input('day_slider', 'value')])
def refresh_agp_graph_callback(n_interval_load, n_startup_interval, checkbox_values, slider_value):
    num_days = [7, 14, 30, 90, 365][slider_value - 1]
    last_loaded = "last refresh {}".format(datetime.now().strftime("%H:%M:%S"))
    start_datetime = datetime.now() - timedelta(days=num_days)
    df = database.get_entries(start_datetime, update=True)
    if df is None:
        logger.warning("didn't receive any data...")
        return [blank_graph(id='top_graph', height="85vh"),
                "didn't receive any data,..."+last_loaded,
                get_headline(None)]
    else:
        return [top_graph(df=df,
                          show_today="show_today" in checkbox_values,
                          show_days="show_days" in checkbox_values,
                          show_grid="show_grid" in checkbox_values,
                          centered="is_centered" in checkbox_values),
                last_loaded,
                get_headline(df.loc[df[DATETIME_COLUMN].idxmax()])]


"""
@app.callback([Output('tir_bars', 'figure')],
              [Input('update_tir_interval', 'n_intervals'),
               Input('startup_interval', 'n_intervals')])
def refresh_tir_graph(n_intervals,n_startup_interval):
    sub_frame = database.get_entries(70)
    result = cgm.agg_weekly(sub_frame)

    if result is None:
        return [{'data': [{'x': [], 'y': [], 'type': 'bar'}],
                 'layout': go.Layout(margin={'l': 40, 'b': 40, 't': 10, 'r': 10})}]

    hypos = np.array([r[0] for r in result[1]])
    range = np.array([r[1] for r in result[1]])
    hyprs = np.array([r[2] for r in result[1]])
    return [{'data': [go.Bar(x=result[0], y=hypos, name='hypos', marker=go.bar.Marker(color=colors["signal"]), hoverinfo="y+x", hovertemplate='%{y:3.1%}'),
                      go.Bar(x=result[0], y=range, name='in range', marker=go.bar.Marker(color=colors["second"]), hoverinfo="y+x", hovertemplate='%{y:3.1%}'),
                      go.Bar(x=result[0], y=hyprs, name='hypers', marker=go.bar.Marker(color=colors["bright"]), hoverinfo="y+x", hovertemplate='%{y:3.1%}')],
             'layout': go.Layout(yaxis=dict(fixedrange=True),
                                 xaxis=dict(fixedrange=True),
                                 barmode='stack', margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
                                 plot_bgcolor=colors['background'],
                                 paper_bgcolor=colors['background'],
                                 showlegend=False,

                                 font={'color': colors['text']})}]
"""

if __name__ == '__main__':
    debug = False
    if "-debug" in sys.argv:
        logger.info("starting application in debug")
        debug = True
    else:
        logger.info("starting application")
    app.run_server(debug=debug, port=8080, host='0.0.0.0')
