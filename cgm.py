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


def calculate_hourly_stats(df, datetime_column, glucose_column, interpolated=True):
    def percentile(n):
        def percentile_(x):
            return np.percentile(x, n)

        percentile_.__name__ = 'p_%s' % n
        return percentile_

    # group by hour buckets
    df["hour"] = df[datetime_column].apply(lambda x: x.hour + x.minute / 60 + x.second / 3600)
    bins = pd.IntervalIndex.from_breaks(np.arange(-.5, 23.5 + 1, 1))
    df["bin"] = pd.cut(df.hour.apply(lambda x: x - 24 if x > 23.5 else x), bins)

    stats = df.groupby('bin').agg({glucose_column:
                                       [percentile(10), percentile(25), percentile(50),
                                        percentile(75), percentile(90)]})

    stats = stats.reset_index()
    stats = stats.drop("bin", axis=1)
    first_row = stats.iloc[0]
    first_row.name = 24
    stats = stats.append(first_row)

    if interpolated:
        stats = stats.apply(lambda x: interpolate(x), axis=0)

    return stats



def smooth(x, order=1):
    if len(x) < 3:
        return x

    x_new = x
    for i in range(0, order):
        x_new = np.convolve(x_new, np.array([1.0, 4.0, 1.0]) / 6.0, 'valid')
        x_new = np.append(np.append(x[0], x_new), x[-1])
    return x_new


def smooth_split(x, time, order):
    minutes = 15
    i_gaps_geq_5 = np.where(np.diff(time) > np.timedelta64(minutes*60*1000000000))[0]
    splits = np.split(x, i_gaps_geq_5+1)
    return np.concatenate([smooth(split, order=order) for split in splits])


def interpolate(series):
    fun = lambda x, y: CubicSpline(x, y, bc_type='periodic')
    hours = np.linspace(0, 23.99, 200)
    values = fun(series.index.values, series.values)(hours)
    return pd.Series(data=values, index=hours, name=series.name)