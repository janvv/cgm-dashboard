import requests
import logging
from datetime import datetime
from pymongo import MongoClient, DESCENDING

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
