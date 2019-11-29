import pandas as pd
import numpy as np
from scipy.interpolate import CubicSpline


def fraction_ranges(s):
    calc = pd.cut(s, bins=[0, 70, 180, 1000], labels=["hypo", "range", "hyper"]).value_counts() / len(s)
    return calc.hypo, calc.range, calc.hyper


def agg_weekly(df):
    if df is not None:
        df["year"] = df.datetime.apply(lambda x: x.year)
        df["week"] = df.datetime.apply(lambda x: x.week)
        g = df.groupby(["year", "week"])
        agg = g.agg({"glucose": lambda x: fraction_ranges(x)})
        (year_weeks, fractions) = agg.index.values.flatten(), agg.values.flatten()
        labels = ["W{}".format(x[1]) for x in agg.index.values]
        return labels, fractions
    else:
        return None


def calculate_hourly_stats(df, datetime_column, glucose_column, smoothed=False, interpolated=True):

    def percentile(n):
        def percentile_(x):
            return np.percentile(x, n)
        percentile_.__name__ = 'p_%s' % n
        return percentile_

    df['hourD'] = df[datetime_column].apply(lambda x: x.hour)
    stats = df.groupby('hourD').agg({glucose_column: [percentile(10), percentile(25), percentile(50),
                                                      percentile(75), percentile(90)]})


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


def smooth(x, order=1):
    x_new = x
    for i in range(0, order):
        x_new = np.convolve(x_new, np.array([1.0, 4.0, 1.0]) / 6.0, 'valid')
        x_new = np.append(np.append(x[0], x_new), x[-1])
    return x_new


def interpolate(series):
    fun = lambda x, y: CubicSpline(x, y, bc_type='periodic')
    hours = np.linspace(0, 23.99, 200)
    values = fun(series.index.values, series.values)(hours)
    return pd.Series(data=values, index=hours, name=series.name)