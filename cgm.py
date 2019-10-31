from pymongo import MongoClient, ASCENDING, DESCENDING, errors
from configparser import ConfigParser
import logging
import agp
import pandas as pd
from datetime import datetime, timedelta
from matplotlib import pyplot as plt

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

    def load_last_entries(self, n = 24*12):
        """
        :param n: Number of entries to query
        :return: List of tuples (timestamp (seconds), glucose value) or None if error occured
        """
        try:
            entries = self.db['entries']
            results = entries.find({"sgv": {"$gt": 0}}, ["sgv", "date"], sort=[("date", DESCENDING)], limit=n)
            temp = [(r["date"] / 1000, r["sgv"]) for r in results]
            df = pd.DataFrame(data=temp, columns=["timestamp", "glucose"])
            df["date_time"] = df.timestamp.apply(lambda x: datetime.fromtimestamp(x))
            df["hour"] = df.date_time.apply(lambda x: x.hour + x.minute / 60 + x.second / (60 * 60))
            df["date"] = df.date_time.apply(lambda x: x.date())
            return df
        except errors.PyMongoError as e:
            self.logger.error("Error while querying for last entries: \n {}".format(e))
            return None

if __name__ == '__main__':
    access = CGMAccess()
    df = access.load_last_entries(n=7*24*12)
    #plt.plot([1,2,3],[1,2,3]);
    #plt.show()
    if df is not None:
        agp.drawAGP(df, "date", "glucose", True)
        plt.show()
