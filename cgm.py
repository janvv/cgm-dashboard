from pymongo import MongoClient, ASCENDING, DESCENDING, errors
from configparser import ConfigParser
import logging
import agp
import pandas as pd
from datetime import datetime, timedelta, timezone
from matplotlib import pyplot as plt
import time


def fraction_ranges(s):
    calc = pd.cut(s, bins=[0, 70, 180, 1000], labels=["hypo", "range", "hyper"]).value_counts() / len(s)
    return calc.hypo, calc.range, calc.hyper

class CGMAccess:
    def __init__(self):
        self.logger = logging.getLogger("dash.mongo")
        self.logger.info("Connecting to mongo db ...")
        config = ConfigParser()
        config.read('config.ini')
        params = config["MongoDB"]
        url = 'mongodb://{}:{}@{}:{}/{}'.format(params["user"], params["password"], params["host"], params["port"], params["database"])
        self.client = MongoClient(url, retryWrites=False)
        self.db = self.client[params["database"]]

        self.earlierst_query_time = -1
        self.latest_query_time = -1

        self.DATETIME_COLUMN ="datetime"
        self.GLUCOSE_COLUMN = "glucose"
        self.df = pd.DataFrame(columns=[self.DATETIME_COLUMN,self.GLUCOSE_COLUMN])

    def update_entries(self, limit_days=0, skip_hours=0):
        """
        :param n: Number of entries to query
        :return: List of tuples (timestamp (seconds), glucose value) or None if error occured
        """

        if limit_days <0:
            raise AttributeError("num_days {} has to be positive")


        #identify existing data
        now = datetime.now()
        t_end = now.timestamp()-skip_hours*60*60
        t_start = 0 if limit_days == 0 else (now - timedelta(days=limit_days)).timestamp()
        datetime_latest_queried_item = self.latest_query_time

        print("LOOKING FOR : {} - {} ...".format(datetime.fromtimestamp(t_start), datetime.fromtimestamp(t_end)))
        print("EXISTING    : {} - {}".format(datetime.fromtimestamp(self.earlierst_query_time),
                                             datetime.fromtimestamp(self.latest_query_time)))

        if (t_start > self.earlierst_query_time) and (t_start < self.latest_query_time):
            t_start = self.latest_query_time

        try:

            #query missing data
            entries = self.db['entries']
            print("QUERYING    : {} - {}".format(datetime.fromtimestamp(t_start), datetime.fromtimestamp(t_end)))
            results = entries.find({"sgv": {"$gt": 0}, "date": {"$gt": t_start*1000, "$lt": t_end*1000}},
                                   ["sgv", "date"], sort=[("date", DESCENDING)])
            tuples = [(datetime.fromtimestamp(r["date"] / 1000), r["sgv"]) for r in results]

            if len(tuples) > 0:
                print("queried {} new entries".format(len(tuples)))
                temp_df = pd.DataFrame(data=tuples, columns=[self.DATETIME_COLUMN, self.GLUCOSE_COLUMN])
                self.df = self.df.append(temp_df, sort=False, ignore_index=True).drop_duplicates()
                #TODO: ATM  we can not use the last item from the pandas dataframe because it gives a different timestamp (tizezone specific)
                t, g = zip(*tuples)
                datetime_latest_queried_item = max(t).timestamp()
                print("latest found = {}".format(max(t)))
        except errors.PyMongoError as e:
            self.logger.error("Error while querying for last entries: \n {}".format(e))

        else:
            # update query times if successfull
            self.earlierst_query_time = min(t_start, self.earlierst_query_time) if (self.earlierst_query_time != -1) else t_start
            #we can not be sure that db is fast enough to return values immediately, therefore end-time is only updated if we received a value
            #if we would update to t_end right away, we would not find it if it wasnt returned immediately
            self.latest_query_time = datetime_latest_queried_item


    def get_entries(self, n_days=14):
        start_datetime = (datetime.now()-timedelta(days=n_days))
        #print("getting entries > {}".format(start_datetime))

        temp_df = self.df.loc[self.df[self.DATETIME_COLUMN] > start_datetime].sort_values(self.DATETIME_COLUMN)
        #temp_df["datetime"] = temp_df.timestamp.apply(lambda x: datetime.fromtimestamp(x,tz=timezone.utc))
        #temp_df["hour"] = temp_df.datetime.apply(lambda x: x.hour + x.minute / 60 + x.second / (60 * 60))
        #temp_df["date"] = temp_df.datetime.apply(lambda x: x.date())
        return temp_df

    def get_last_entry(self):
            return self.df.loc[self.df[self.DATETIME_COLUMN].idxmax()]

    def get_current_day_entries(self):
        sub_frame = self.get_entries(1)
        todate = datetime.now().date()
        groups = sub_frame.groupby(self.df[self.DATETIME_COLUMN].apply(lambda x: x.date()))
        if todate in groups.groups:
            return groups.get_group(todate)
        else:
            return None

    def agg_last_6_months(self):
        # last_years, last_months = get_last_12_year_months()
        sub_frame = self.df.loc[self.df.datetime > datetime.now() - timedelta(days=182)]
        sub_frame["year"] = sub_frame.datetime.apply(lambda x: x.year)
        sub_frame["month"] = sub_frame.datetime.apply(lambda x: x.month)
        g = sub_frame.groupby(["year", "month"])
        agg = g.agg({"glucose": lambda x: fraction_ranges(x)[1]})

        (year_months, means) = agg.index.values.flatten(), agg.values.flatten()
        labels = [datetime(year=x[0], month=x[1], day=1).strftime("%b '%y") for x in agg.index.values]
        print(labels,means)
        return labels, means


t = None
def tic():
    global t
    t = time.time()
def toc():
    elapsed = time.time() - t
    print("elapsed time {}".format(elapsed))

if __name__ == '__main__':
    import agp
    print("all")
    access = CGMAccess()

    access.update_entries(limit_days=14, skip_hours=10/60)
    df = access.get_entries(14)

    access.update_entries()
    print(access.agg_last_6_months())

