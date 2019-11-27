from configparser import ConfigParser
import logging
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
from adapter import DataBase, MongoAdapter, RestAdapter, Adapter, DATETIME_COLUMN, GLUCOSE_COLUMN

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
        self.logger = logging.getLogger(self.__module__)
        config = ConfigParser()
        config.read('config.ini')
        section = config.sections()[0]

        #connect to datbase
        self.database = None
        if section == "MongoDB":
            self.logger.info("Using MongoDB Adapter ...")
            adapter = MongoAdapter(config["MongoDB"])
            self.database = DataBase(adapter)
        elif section == "REST":
            self.logger.info("Using REST Adapter...")
            adapter = RestAdapter(config["REST"])
            self.database = DataBase(adapter)

    def get_entries(self, n_days=14, update=True):
        return self.database.get_entries(n_days, update=update)

    def get_last_entry(self, update=False):
        df = self.database.get_entries(1, update=update)
        if df is not None:
            return df.loc[df[DATETIME_COLUMN].idxmax()]
        else:
            return None

    def get_current_day_entries(self, update=False):
        sub_frame = self.database.get_entries(1, update=update)
        if sub_frame is not None:
            to_date = datetime.now().date()
            groups = sub_frame.groupby(sub_frame[DATETIME_COLUMN].apply(lambda x: x.date()))
            if to_date in groups.groups:
                result = groups.get_group(to_date)
                return result
        return None

    def agg_last_6_months(self):
        sub_frame = self.database.get_entries(70)
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
    df = access.get_current_day_entries(True)
    print(df)
    #groups = df.groupby(df[access.DATETIME_COLUMN].apply(lambda x: x.date()))
    #for date,sub_frame in groups:
    #    sub_frame.plot.plot()
    #toc()

