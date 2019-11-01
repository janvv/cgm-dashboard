import numpy as np
from datetime import datetime, timedelta, time
from scipy import interpolate as interp
from matplotlib import pyplot as plt


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


def calculateHourlyStats(logs, column_name_datetime, glucose_column_name, smoothed=False, interpolate=True):
    def std(df):
        return np.sqrt(df.var())

    def percentile(n):
        def percentile_(x):
            return np.percentile(x, n)

        percentile_.__name__ = 'p_%s' % n
        return percentile_

    logs['hourD'] = logs[column_name_datetime].apply(lambda x: x.hour)
    stats = logs.groupby('hourD').agg({glucose_column_name: [percentile(10), percentile(25),
                                                             percentile(50), percentile(75),
                                                             percentile(90)]})


    # smooth using convolutional filter
    p90 = smooth(stats.glucose.p_90.values) if smoothed else stats.glucose.p_90
    p75 = smooth(stats.glucose.p_75.values) if smoothed else stats.glucose.p_75
    p50 = smooth(stats.glucose.p_50.values) if smoothed else stats.glucose.p_50
    p25 = smooth(stats.glucose.p_25.values) if smoothed else stats.glucose.p_25
    p10 = smooth(stats.glucose.p_10.values) if smoothed else stats.glucose.p_10
    hours = stats.index

    # copy first value to the end -> 24.00 equals 00:00
    hours = np.append(hours, 24)
    p90 = np.append(p90, p90[0])
    p75 = np.append(p75, p75[0])
    p50 = np.append(p50, p50[0])
    p25 = np.append(p25, p25[0])
    p10 = np.append(p10, p10[0])

    # interpolate using splines
    if interpolate:
        temp = hours
        hours = np.linspace(0, 24, 100)
        interp_fun = lambda x, y: interp.CubicSpline(x, y, bc_type='periodic')
        p90 = interp_fun(temp, p90)(hours)
        p75 = interp_fun(temp, p75)(hours)
        p50 = interp_fun(temp, p50)(hours)
        p25 = interp_fun(temp, p25)(hours)
        p10 = interp_fun(temp, p10)(hours)

    return hours, p10, p25, p50, p75, p90


def drawHourlyStats(logs, column_name_datetime, column_name_glucose, a=None):
    stats = calculateHourlyStats(logs, column_name_datetime, column_name_glucose)
    if not a:
        a = plt.figure(figsize=(14, 5)).gca()
    a.bar(list(stats.index), stats.p_90 - stats.p_10, 0.8, stats.p_10, alpha=0.3, color='b')
    a.bar(list(stats.index), stats.p_75 - stats.p_25, 0.8, stats.p_25, alpha=0.5, color='b')
    a.bar(list(stats.index), height=np.repeat(3, 24), width=0.8, bottom=stats.p_50 - 1.5, color='k', alpha=1)


def smooth(x, order = 1):
    x_new = x
    for i in range(0,order):
        x_new = np.convolve(x_new, np.array([1.0, 4.0, 1.0]) / 6.0, 'valid')
        x_new = np.append(np.append(x[0], x_new), x[-1])
    return x_new


def fillColorized(a, X, Ylow, Ytop, thresh_bottom, thresh_top):
    bottom1 = np.array([max(thresh_top, y) for y in Ylow])
    top1 = np.array([max(thresh_top, y) for y in Ytop])
    plt.fill_between(X, bottom1, top1, color='r', linewidth=0, alpha=0.5)

    top2 = np.array([min(thresh_bottom, y) for y in Ytop])
    bottom2 = np.array([min(thresh_bottom, y) for y in Ylow])
    plt.fill_between(X, bottom2, top2, color='b', linewidth=0, alpha=0.5)

    top3 = np.array([min(bottom1[i], Ytop[i]) for i in range(0, len(Ytop))])
    bottom3 = np.array([max(top2[i], Ylow[i]) for i in range(0, len(Ytop))])
    plt.fill_between(X, bottom3, top3, color='g', linewidth=0, alpha=0.5)


def major_formatter(x):
    if x == 24:
        d = time(hour=23, minute=59, second=59)
    else:
        d = time(hour=np.mod(x, 24))
    return d.strftime('%H:%M')
