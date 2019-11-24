import numpy as np
from datetime import datetime, timedelta, time
from scipy import interpolate as interp
from matplotlib import pyplot as plt
import pandas as pd

def getLogs(logs, user_id, numberDays=14):
    user_logs = logs.loc[logs.user_id == user_id]
    start_date = user_logs.date.max() - timedelta(days=numberDays)
    return user_logs.loc[user_logs.date > start_date]


def drawDayTraces(logs, column_name_date, column_name_datetime, column_name_glucose):
    day_groups = logs.groupby(column_name_date)
    for date, logs in day_groups:
        hours = logs[column_name_datetime].apply(lambda x: x.hour + x.minute / 60.0).values
        measurements = logs[column_name_glucose].values
        plt.plot(hours, measurements, '.-', label=date, alpha=0.5)


def calculateHourlyStats(logs, datetime_column, glucose_column, smoothed=False, interpolated=True):

    def percentile(n):
        def percentile_(x):
            return np.percentile(x, n)

        percentile_.__name__ = 'p_%s' % n
        return percentile_

    logs['hourD'] = logs[datetime_column].apply(lambda x: x.hour)
    stats = logs.groupby('hourD').agg({glucose_column: [percentile(10), percentile(25),
                                                             percentile(50), percentile(75),
                                                             percentile(90)]})


    # smooth using convolutional filter
    if smoothed:
        stats = stats.apply(lambda x: smooth(x.values), axis=0)

    # copy first value to the end -> 24.00 equals 00:00
    first_row = stats.loc[0]
    first_row.name = 24
    stats = stats.append(first_row)

    # interpolate using splines
    if interpolated:
        stats = stats.apply(lambda x: interpolate(x), axis=0)
    return stats


def smooth(x, order = 1):
    x_new = x
    for i in range(0,order):
        x_new = np.convolve(x_new, np.array([1.0, 4.0, 1.0]) / 6.0, 'valid')
        x_new = np.append(np.append(x[0], x_new), x[-1])
    return x_new

def interpolate(series):
    fun = lambda x, y: interp.CubicSpline(x, y, bc_type='periodic')
    hours = np.linspace(0, 23.99, 200)
    values = fun(series.index.values, series.values)(hours)
    return pd.Series(data=values, index=hours, name=series.name)

def fillColorized(ax, X, Ylow, Ytop, thresh_bottom, thresh_top):
    bottom1 = np.array([max(thresh_top, y) for y in Ylow])
    top1 = np.array([max(thresh_top, y) for y in Ytop])
    ax.fill_between(X, bottom1, top1, color='r', linewidth=0, alpha=0.25)

    top2 = np.array([min(thresh_bottom, y) for y in Ytop])
    bottom2 = np.array([min(thresh_bottom, y) for y in Ylow])
    ax.fill_between(X, bottom2, top2, color='r', linewidth=0, alpha=0.25)

    top3 = np.array([min(bottom1[i], Ytop[i]) for i in range(0, len(Ytop))])
    bottom3 = np.array([max(top2[i], Ylow[i]) for i in range(0, len(Ytop))])
    ax.fill_between(X, bottom3, top3, color='g', linewidth=0, alpha=0.5)


def major_formatter(x):
    if x == 24:
        d = time(hour=23, minute=59, second=59)
    else:
        d = time(hour=np.mod(x, 24))
    return d.strftime('%H:%M')


def drawAGP(logs, column_name_datetime, column_name_glucose,
            color='b', show_threshs=False, smoothed=False, interpolated=True, ax=None):

    # calculate percentiles
    stats = calculateHourlyStats(logs, column_name_datetime, column_name_glucose,
                                 smoothed=smoothed, interpolated=interpolated)
    stats = stats.sort_index()

    # draw
    if not ax:
        ax = plt.figure(figsize=(12, 5)).gca()
    ax.grid(True, 'both')
    if show_threshs:
        ax.hlines([70, 180], 0, 24, colors=['r', 'b'], linestyles='--')

    # percentiles
    ax.plot(stats.index.values, stats.glucose.p_50.values, color=color, linewidth='4', label='median')
    ax.fill_between(stats.index.values, stats.glucose.p_10.values, stats.glucose.p_90.values, color=color, alpha=0.3, label='90th')
    ax.fill_between(stats.index.values, stats.glucose.p_25.values, stats.glucose.p_75.values, color=color, alpha=0.5, label='25th')
    ax.legend(loc='upper right', frameon=False)

    # axis labels
    x_pos = [0, 6, 12, 18, 24]
    ax.set_xticks(x_pos)
    ax.set_xticklabels([major_formatter(x) for x in x_pos]);
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Glucose in mg/dl')
    ax.set_ylim([35, 350])
    ax.set_yticks([70, 140, 180, 250, 300])
    ax.set_xlim([0, 24])

    return ax
