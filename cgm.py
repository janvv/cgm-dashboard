from pymongo import MongoClient, ASCENDING, DESCENDING, errors
from configparser import ConfigParser
import logging
import pandas as pd
from datetime import datetime, timedelta, timezone
import time

t = None
def tic():
    global t
    t = time.time()
def toc():
    elapsed = time.time() - t
    print("elapsed time {}".format(elapsed))


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
            return False
        else:
            # update query times if successfull
            self.earlierst_query_time = min(t_start, self.earlierst_query_time) if (self.earlierst_query_time != -1) else t_start
            #we can not be sure that db is fast enough to return values immediately, therefore end-time is only updated if we received a value
            #if we would update to t_end right away, we would not find it if it wasnt returned immediately
            self.latest_query_time = datetime_latest_queried_item
            return True


    def get_entries(self, n_days=14, update = True):
        start_datetime = (datetime.now()-timedelta(days=n_days))

        #check if we need to update data
        if update and (((datetime.now().timestamp()-self.latest_query_time) > 1*60) or (start_datetime.timestamp() < self.earlierst_query_time)):
            print("updating condition met")
            success = self.update_entries(n_days)
            if not success:
                return None
        sub_frame = self.df.loc[self.df[self.DATETIME_COLUMN] > start_datetime].sort_values(self.DATETIME_COLUMN)
        if len(sub_frame) > 0:
            return sub_frame
        else:
            return None

    def get_last_entry(self, update=False):
        df = self.get_entries(1, update=update)
        if df is not None:
            return df.loc[df[self.DATETIME_COLUMN].idxmax()]
        else:
            return None


    def get_current_day_entries(self, update = False):
        sub_frame = self.get_entries(1, update=update)
        if sub_frame is not None:
            to_date = datetime.now().date()
            groups = sub_frame.groupby(self.df[self.DATETIME_COLUMN].apply(lambda x: x.date()))
            if to_date in groups.groups:
                result = groups.get_group(to_date)
                return result
        return None

    def agg_last_6_months(self):
        sub_frame = self.get_entries(70)
        if sub_frame is not None:
            sub_frame["year"] = sub_frame.datetime.apply(lambda x: x.year)
            sub_frame["week"] = sub_frame.datetime.apply(lambda x: x.week)
            g = sub_frame.groupby(["year", "week"])

            agg = g.agg({"glucose": lambda x: fraction_ranges(x)})
            (year_weeks, fractions) = agg.index.values.flatten(), agg.values.flatten()
            labels = ["W{}".format(x[1]) for x in agg.index.values]

            return labels, fractions
        else:
            return None


if __name__ == '__main__':
    access = CGMAccess()

    tic()
    agg = access.agg_last_6_months()
    print(agg)
    toc()

