import requests
import logging
from datetime import datetime
from pymongo import MongoClient, DESCENDING
import numpy as np
import math
import logging
class Adapter:
    logger = logging.getLogger(__name__)
    def __init__(self):
        pass

    def query(self, t_start, t_end):
        """

        :param t_start: posix timestamp
        :param t_end:  posix timestamp
        :return:
        """
        return []

class MongoAdapter(Adapter):
    def __init__(self, params):
        super().__init__()
        url = 'mongodb://{}:{}@{}:{}/{}'.format(params["user"], params["password"], params["host"], params["port"], params["database"])
        self.client = MongoClient(url, retryWrites=False)
        self.db = self.client[params["database"]]
        self.logger = logging.getLogger(self.__module__)
        self.logger.setLevel(logging.ERROR)
        self.collection = params["collection"]

    def query(self, t_start, t_end):
        self.logger.info("querying entries between {} to {}".format(t_start, t_end))

        # query missing data
        entries = self.db[self.collection]
        print(entries)
        self.logger.info("QUERYING    : {} - {}".format(datetime.fromtimestamp(t_start), datetime.fromtimestamp(t_end)))
        results = entries.find({"sgv": {"$gt": 0}, "date": {"$gte": t_start * 1000, "$lte": t_end * 1000}},
                               ["sgv", "date"], sort=[("date", DESCENDING)])
        tuples = [(datetime.fromtimestamp(r["date"] / 1000), r["sgv"]) for r in results]
        return tuples
        
class MongoAdapterSRV(MongoAdapter):
    def __init__(self, params):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.ERROR)
        self.collection = params["collection"]
        try:
            url = "mongodb+srv://{user}:{password}@{cluster_url}/{database}?retryWrites=true&w=majority".format(**params)
            self.client = MongoClient(url)
            self.db = self.client[params["database"]]
        except Exception as e:
            self.logger.exception("this didn't work")


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
        return tuples

