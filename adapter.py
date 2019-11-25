from pymongo import MongoClient, ASCENDING, DESCENDING, errors
import logging
import pandas as pd
from datetime import datetime, timedelta, timezone

DATETIME_COLUMN = "datetime"
GLUCOSE_COLUMN = "glucose"

class DataBase:

    def __init__(self, adapter):
        self.logger = logging.getLogger(self.__module__)
        self.logger.info("Connecting to mongo db ...")

        self.earlierst_query_time = -1
        self.latest_query_time = -1

        self.df = pd.DataFrame(columns=[DATETIME_COLUMN, GLUCOSE_COLUMN])

        self.adapter = adapter

    def update_entries(self, limit_days=0, skip_hours=0):
        """
        :param n: Number of entries to query
        :return: List of tuples (timestamp (seconds), glucose value) or None if error occured
        """

        if limit_days < 0:
            raise AttributeError("num_days {} has to be positive")

        # identify existing data
        now = datetime.now()
        t_end = now.timestamp() - skip_hours * 60 * 60
        t_start = 0 if limit_days == 0 else (now - timedelta(days=limit_days)).timestamp()
        datetime_latest_queried_item = self.latest_query_time

        print("LOOKING FOR : {} - {} ...".format(datetime.fromtimestamp(t_start), datetime.fromtimestamp(t_end)))
        print("EXISTING    : {} - {}".format(datetime.fromtimestamp(self.earlierst_query_time),
                                             datetime.fromtimestamp(self.latest_query_time)))

        # data before and after start of query range exists -> only search for missing data
        if (t_start > self.earlierst_query_time) and (t_start < self.latest_query_time):
            t_start = self.latest_query_time

        try:
            tuples = self.adapter.query(t_start, t_end)
            if len(tuples)>0:
                if len(tuples) > 0:
                    print("queried {} new entries".format(len(tuples)))
                    temp_df = pd.DataFrame(data=tuples, columns=[DATETIME_COLUMN, GLUCOSE_COLUMN])
                    self.df = self.df.append(temp_df, sort=False, ignore_index=True).drop_duplicates()
                    # TODO: ATM  we can not use the last item from the pandas dataframe because it gives a different timestamp (tizezone specific)
                    t, g = zip(*tuples)
                    datetime_latest_queried_item = max(t).timestamp()
                    print("latest found = {}".format(max(t)))

        except errors.PyMongoError as e:
            self.logger.error("Error while querying for last entries: \n {}".format(e))
            return False
        else:
            # update query times if successfull
            self.earlierst_query_time = min(t_start, self.earlierst_query_time) if (
                        self.earlierst_query_time != -1) else t_start
            # we can not be sure that db is fast enough to return values immediately, therefore end-time is only updated if we received a value
            # if we would update to t_end right away, we would not find it if it wasnt returned immediately
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
        sub_frame = self.df.loc[self.df[DATETIME_COLUMN] > start_datetime].sort_values(DATETIME_COLUMN)
        if len(sub_frame) > 0:
            return sub_frame
        else:
            return None

class Adapter:
    def __init__(self):
        pass

    def query(self, t_start, t_end):
        return []

class MongoAdapter(Adapter):
    def __init__(self, params):
        super().__init__()
        url = 'mongodb://{}:{}@{}:{}/{}'.format(params["user"], params["password"], params["host"], params["port"], params["database"])
        self.client = MongoClient(url, retryWrites=False)
        self.db = self.client[params["database"]]

    def query(self, t_start, t_end):
        # query missing data
        entries = self.db['entries']
        print("QUERYING    : {} - {}".format(datetime.fromtimestamp(t_start), datetime.fromtimestamp(t_end)))
        results = entries.find({"sgv": {"$gt": 0}, "date": {"$gt": t_start * 1000, "$lt": t_end * 1000}},
                               ["sgv", "date"], sort=[("date", DESCENDING)])
        tuples = [(datetime.fromtimestamp(r["date"] / 1000), r["sgv"]) for r in results]
        return tuples
