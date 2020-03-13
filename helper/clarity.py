import pandas as pd
from datetime import datetime, timedelta

def convert(x, low_description='Niedrig'):
    try:
        value = float(x)
    except ValueError:
        if x.lower() == "low":
            value = 40
        elif x.lower() == "high":
            value = 400
        else:
            raise ValueError("can't decompile {}".format(x))
    return float(value)
    #elif x == low_description:
    #    return 30
    #else:
    #    return 400

def day_of_year(date):
    return  date.timetuple().tm_yday

def load_clarity_csv(pathname):
    df = pd.read_csv(pathname)
    #rename
    columns = ["index",
               "datetime",
               "event_type",
               "event_subtype",
               "patient_info",
               "device_info",
               "source_id",
               "glucose",
               "insulin",
               "carbohydrates",
               "duration",
               "roc",
               "transmitter_time",
               "transmitter_id"]
    df = df.rename(columns = dict(zip(df.columns.values, columns)))

    #remove unnecessary columns
    #cols_to_remove = set(columns).symmetric_difference(["datetime", "glucose"])
    df = df[["datetime", "glucose"]]
    df = df.dropna(how="any")


    df["datetime"] = df.datetime.apply(lambda x: datetime.strptime(x, "%Y-%m-%dT%H:%M:%S"))
    #df["timestamp_seconds"] = df.datetime.apply(lambda x: x.timestamp())
    df["glucose"] = df.glucose.apply(lambda x: convert(x))
    #df["year"] = df.datetime.apply(lambda x: x.year)
    #df["day_of_year"] = df.datetime.apply(lambda x: day_of_year(x))
    #df = df.rename(columns={glucose_col: "sgv", date_col: "date"})
    
    return df
