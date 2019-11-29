import requests
import logging
from datetime import datetime
from pymongo import MongoClient, DESCENDING
import numpy as np
import math
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


class RestAdapter(Adapter):
    def __init__(self, params):
        super().__init__()
        self.logger = logging.getLogger(self.__module__)
        self.url = 'https://{}:{}/api/v1/entries/sgv.json'.format(params["domain"], params["port"])

    def query(self, t_start, t_end):
        '# add count=100000 to circument some bad REST implementations'
        'which limit results even when specifying date range'
        params = {"find[date][$gt]": int(t_start*1000),
                  "find[date][$lt]": int(t_end*1000),
                  "count": max(100000, 20*(t_end-t_start)/(60*60))}
        response = requests.get(self.url, params=params)
        tuples = [(datetime.fromtimestamp(j["date"] / 1000), #, timezone(timedelta(minutes=j["utcOffset"]))),
                   j["sgv"]) for j in response.json()]
        self.logger.info("queried {} tuples".format(len(tuples)))
        return tuples

class OfflineAdapter(Adapter):
    @staticmethod
    def roundup(x, thresh):
        return int(math.ceil(x / thresh)) * thresh

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__module__)

    def query(self, t_start, t_end):
        t0r = OfflineAdapter.roundup(t_start, 10*60)
        t1r = OfflineAdapter.roundup(t_end, 10*60)

        times = np.arange(t0r, t1r, 10*60)
        glucose = 160 + np.sin(times*np.pi*2/(6*3600))*80# + np.random.rand(len(times))*20
        datetimes = [datetime.fromtimestamp(t) for t in times]
        tuples = list(zip(datetimes, glucose))
        print(list(zip(datetimes, glucose)))
        return tuples
