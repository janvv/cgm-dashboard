from pymongo import MongoClient, ASCENDING, DESCENDING, errors
from configparser import ConfigParser
import logging
import agp
import pandas as pd
from datetime import datetime, timedelta, timezone
from matplotlib import pyplot as plt
import time

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
        self.df = pd.DataFrame(columns=["timestamp", "glucose"])
        self.earlierst_query_time = -1
        self.latest_query_time = -1
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

        #print("LOOKING FOR : {} - {} ...".format(t_start, t_end))
        #print("EXISTING    : {} - {}".format(self.earlierst_query_time, self.latest_query_time))

        if (t_start > self.earlierst_query_time) and (t_start < self.latest_query_time):
            t_start = self.latest_query_time

        if t_end-t_start < 10:
            print("IGNORE because time since last query < 10 seconds")
        else:
            try:

                #query missing data
                entries = self.db['entries']
                #print("QUERYING   : {} - {}".format(t_start, t_end))
                results = entries.find({"sgv": {"$gt": 0}, "date": {"$gt": t_start*1000, "$lt": t_end*1000}},
                                       ["sgv", "date"], sort=[("date", DESCENDING)])
                temp = [(r["date"] / 1000, r["sgv"]) for r in results]

                if len(temp) > 0:
                    temp_df = pd.DataFrame(data=temp, columns=["timestamp", "glucose"])
                    print("queried {} new entries".format(len(temp_df)))
                    self.df = self.df.append(temp_df, sort=True, ignore_index=True).drop_duplicates()

            except errors.PyMongoError as e:
                self.logger.error("Error while querying for last entries: \n {}".format(e))

            else:
                # update query times if successfull
                self.earlierst_query_time = min(t_start, self.earlierst_query_time) if (self.earlierst_query_time != -1) else t_start
                self.latest_query_time = t_end


    def get_entries(self, n_days=14):
        start_datetime = (datetime.now()-timedelta(days=n_days)).timestamp()
        #print("getting entries > {}".format(start_datetime))

        temp_df = self.df.loc[self.df.timestamp > start_datetime]
        temp_df["datetime"] = temp_df.timestamp.apply(lambda x: datetime.fromtimestamp(x,tz=timezone.utc))
        temp_df["hour"] = temp_df.datetime.apply(lambda x: x.hour + x.minute / 60 + x.second / (60 * 60))
        temp_df["date"] = temp_df.datetime.apply(lambda x: x.date())
        return temp_df

t = None
def tic():
    global t
    t = time.time()
def toc():
    elapsed = time.time() - t
    print("elapsed time {}".format(elapsed))

if __name__ == '__main__':
    print("all")
    access = CGMAccess()

    access.update_entries(0.2,skip_hours=1)
    df = access.get_entries(1)
    print(df.head())
    print(df.tail())
    df.to_json()
    print("check1")

    access.update_entries(0.2, skip_hours=0)
    df = access.get_entries(1)
    print(df)
    df.to_json()
    print("check2")

