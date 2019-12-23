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
from adapter import MongoAdapter, RestAdapter, OfflineAdapter
from database import DataBase, DATETIME_COLUMN, GLUCOSE_COLUMN
from datetime import datetime, time, timedelta

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css',
                        'https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

logger = logging.getLogger(__name__)

#setup database and backend adapter
config = ConfigParser()
config.read('config.ini')
section = config.sections()[0]
if section == "MongoDB":
    logger.info("Connecting to MongoDB")
    adapter = MongoAdapter(config["MongoDB"])
elif section == "REST":
    logger.info("Connecting to REST")
    adapter = RestAdapter(config["REST"])
elif section == "OFFLINE":
    adapter = OfflineAdapter()
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
    stats = cgm.calculate_hourly_stats(df, datetime_column=DATETIME_COLUMN, glucose_column=GLUCOSE_COLUMN, interpolated=True)

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


def top_graph(df, show_today=True, show_grid=True, centered=False):
    ylim = 350
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

        #remove close grid lines

        ticks[ticks < start] += 24
        ticks = ticks[~(np.abs(now_hour - ticks) <= 1.5)]
        #ticks = ticks[~((now_hour - ticks) <= -22.5)]
        ticks = np.append(ticks, now_hour if now_hour >= start else now_hour + 24)

        print(ticks)

    print("start={} end = {}".format(start, end))

    graphs = []
    try:
        graphs = graphs + agp_components(df, start)
    except Exception as e:
        print("error creating AGP: {}".format(e))


    #get last day cgm data
    annotations = []
    if show_today:
        try:
            df_last_day = database.get_entries(1)
            df_last_day["hour"] = df_last_day[DATETIME_COLUMN].apply(lambda x: x.hour + x.minute / 60 + x.second / 3600)

            if df_last_day is not None:
                if centered:
                    cut_off = datetime.now() - timedelta(hours=24.0 - preview)#prevent warping
                else:
                    cut_off = datetime.now().date()#beginning of today

                df_last_day = df_last_day.loc[df_last_day[DATETIME_COLUMN] > cut_off]
                df_last_day.loc[df_last_day.hour < start, "hour"] = df_last_day[df_last_day.hour < start].hour + 24
                hours = df_last_day.hour.values
                time_strings = df_last_day[DATETIME_COLUMN].apply(lambda x: x.strftime("%H:%M")).values

                glucose = np.array(df_last_day[GLUCOSE_COLUMN].values, dtype=int)
                glucose_smoothed = cgm.smooth_split(glucose, hours, order=6)

                last_day_graph = [go.Scatter(x=hours, y=glucose,
                                             marker=dict(size=1, color="#808080",
                                                         line=dict(color="white", width=1)),
                                             mode="markers", hoverinfo="none",
                                             showlegend=False)]
                graphs = graphs + last_day_graph



                filtered_graph = [go.Scatter(x=hours[:-1], y=glucose_smoothed[:-1],
                                             marker=dict(size=7, color=colors["bright"],
                                                         line=dict(color="white", width=1)),
                                             text=time_strings[:-1], mode="markers", hoverinfo="y+text",
                                             hovertemplate='%{y:3.0f} mg/dl <br> %{text}',
                                             showlegend=False)]
                graphs = graphs + filtered_graph

                if datetime.now() - df_last_day[DATETIME_COLUMN].iloc[-1] < timedelta(minutes=15):
                    print(hours[-1],glucose_smoothed[-1],time_strings[-1])

                    last_glucose_dot = [go.Scatter(x=[hours[-1]], y=[glucose_smoothed[-1]],
                                                 marker=dict(size=15, color=colors["bright"],
                                                             line=dict(color="white", width=3)),
                                                 text=[time_strings[-1]],
                                                 mode="markers", hoverinfo="y+text",
                                                 hovertemplate='%{y:3.0f} mg/dl <br> %{text}',
                                                 showlegend=False)]
                    graphs = graphs + last_glucose_dot
                #add annotation if glucose is up to date
                #if datetime.now() - df_last_day[DATETIME_COLUMN].iloc[-1] < timedelta(minutes=15):
                #    go.Scatter()
                #    annotations.append(dict(x=min(max(start+2, hours[-1]), end-2), y=glucose[-1], xref="x", yref="y",
                #                            text='{:03d}'.format(int(glucose[-1])), showarrow=True, arrowhead=0,
                #                            ax=0, ay=-250, align = "center",
                #                            font=dict(size=64, color=colors["text"]), arrowcolor=colors['text']))

                else:
                    print("latest cgm too old -> don't add annotation")

                graphs = graphs + last_day_graph
        except Exception as e:
            print("Error while adding day scatter plot: {}".format(e))
    return {
        'data': graphs,
        'layout': go.Layout(
            xaxis=dict(type='linear', zeroline=False, range=[start, end],
                       ticktext=[major_formatter(x) for x in ticks], fixedrange=True,
                       tickvals=ticks, gridcolor='#808080', showgrid=show_grid),
            yaxis=dict(type='linear', zeroline=False, range=[40, ylim], #title='glucose',
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
        minutes = (datetime.now() - latest[DATETIME_COLUMN]).seconds/60

        container = html.Div if minutes < 15 else html.Del
        color = colors["text"] if minutes < 15 else "#808080"
        return html.Div(children=[container(" {:.0f} ".format(latest[GLUCOSE_COLUMN]),
                                            style={'display': 'inline-block', "font-size": 64, 'color': color}),
                                  html.Div("mg/dl".format(latest[GLUCOSE_COLUMN]),
                                            style={'marginLeft': 8, 'marginRight': 16, 'display': 'inline-block', "font-size": 24, 'color': color})],
                        style={'textAlign': 'right'})
    else:
        return html.Div("???")


app.layout = html.Div(style={"height": "100vh", "width": "100vw", 'backgroundColor': colors['background'],
                             'color': colors['text']}, children=[
    html.Div(id="title", style={'textAlign': 'right','height': '15vh'}),

    html.Div(children=[blank_graph(id='top_graph', height="75vh")]),

    html.Div(style={'display': 'inline-block', 'height':'10vh'}, children=[
        html.Div(id='last_loaded_div', children="Last Refresh: ???", style={'width': '200px', 'display': 'inline-block', 'text-align': 'center'}),
        dcc.Checklist(id="checkboxes",
                      options=[{'label': 'Today', 'value': 'show_today'},
                               {'label': 'Center', 'value': 'is_centered'},
                               {'label': 'Grid', 'value': 'show_grid'}],
                      value=['show_today', 'is_centered', 'show_grid'],
                      labelStyle={'display': 'inline-block'},
                      style={'display': 'inline-block'}),
        html.Div(dcc.Slider(id="day_slider", min=1, max=5, step=1, value=2,
                            marks=dict(zip([1, 2, 3, 4, 5], ["7d", "14d", "30d", "90d", "365d"]))),
                 style={"width": 200, "marginLeft": 20, 'display': 'inline-block'})]),

    #blank_graph(id="tir_bars", height="20vh"),
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
    df = database.get_entries(num_days, update=True)
    latest = database.get_last_entry(update=False)
    return [top_graph(df=df,
                      show_today="show_today" in checkbox_values,
                      show_grid="show_grid" in checkbox_values,
                      centered="is_centered" in checkbox_values),
            last_loaded, get_headline(latest)]

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
        print("starting in debug")
        debug = True
    app.run_server(debug=debug, port=8080, host='0.0.0.0')
