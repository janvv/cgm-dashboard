from pymongo import MongoClient, DESCENDING
import logging
import numpy as np
import math
import requests
from datetime import datetime


def convert_glucose_to_nightscout_format(df, df_glucose_col, df_date_col):
    # convert to mongo nightscout format
    temp = df.copy()
    temp = temp[[df_date_col, df_glucose_col]]
    temp = temp.rename(columns={df_glucose_col: "sgv", df_date_col: "date"})
    temp["date"] = temp["date"].apply(lambda x: x.to_pydatetime().timestamp() * 1000)
    records = temp.to_dict('records')
    return records

class MongoUploader():
    def __init__(self, client, db_name):
        super().__init__()

        """url = 'mongodb://{}:{}@{}:{}/{}'.format(params["user"],
                                                params["password"],
                                                params["host"],
                                                params["port"],
                                                params["database"])
        """
        glucose_col = "sgv"
        date_col = "date"
        #self.client = MongoClient(url, retryWrites=False)
        #self.db = self.client[params["database"]]
        self.client = client
        self.db = self.client[db_name]
        self.logger = logging.getLogger(self.__module__)
        self.logger.setLevel(logging.ERROR)

        # get the list of available collections, call them tables for fun
        tables = self.db.list_collection_names(include_system_collections=False)
        print("TABLES:\n", tables)

    def upload_glucose(self, df, df_glucose_col, df_date_col, perform_test = False):
        #remove old entries in that time range
        t_max = df[df_date_col].max().to_pydatetime().timestamp() * 1000
        t_min = df[df_date_col].min().to_pydatetime().timestamp() * 1000
        print(t_min,t_max)
        
        collection = self.db["entries" if not perform_test else "test_entries"]

        if collection.find_one(sort=[("date",1)]) is not None: # not empty
            min_ = collection.find_one(sort=[("date",1)])
            max_ = collection.find_one(sort=[("date",-1)])["date"]
            print(min_, max_)

            #remove old entries
            print(collection.count()," currently in table")

            f = collection.find({"date": {"$lte": t_max, "$gte": t_min}})
            print(f.count()," to be removed")

            collection.remove({"date": {"$lte": t_max, "$gte": t_min}})
            print(collection.count()," after remove")

        records = convert_glucose_to_nightscout_format(df, df_glucose_col, df_date_col)

        print(len(records), " to be added")
        #insert new values
        collection.insert_many(records)

        print(collection.count(), " after adding new values")



    def upload_insulin(self, df, df_insulin_col, df_date_col, perform_test=False):
        """{
            "_id": {
                "$oid": "5e6551b3e3ec3ccbc922460c"
            },
            "enteredBy": "",
            "eventType": "<none>",
            "reason": "",
            "protein": "",
            "fat": "",
            "insulin": 3,
            "duration": 0,
            "created_at": "2020-03-08T19:12:00.000Z",
            "utcOffset": 0
        }"""
        print(df_date_col)

        #remove old entries in that time range
        t_max = df[df_date_col].max().timestamp() * 1000
        t_min = df[df_date_col].min().timestamp() * 1000
        collection = self.db["treatments" if not perform_test else "test_treatments"]
        collection.remove({"timestamp": {"$lt": t_max, "$gt": t_min}})

        #convert to mongo nightscout format
        temp = df.copy()
        temp = temp[[df_date_col, df_insulin_col]]
        temp = temp.rename(columns={df_insulin_col: "insulin", df_date_col: "created_at"})
        records = temp.to_dict('records')

        #insert new values
        collection.insert_many(records)

