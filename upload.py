from pymongo import MongoClient, DESCENDING
from helper import clarity, uploader
from database import DataBase, DATETIME_COLUMN, GLUCOSE_COLUMN
from datetime import datetime, time, timedelta
from configparser import ConfigParser


#load csvs
df = clarity.load_clarity_csvs_in("csvs")
print(df.head())

config = ConfigParser()
config.read('config.ini')
section = config.sections()[0]
params = config[section]
print(dict(params))

try:
    url = "mongodb+srv://{user}:{password}@{cluster_url}/{database}?retryWrites=true&w=majority".format(**params)
    client = MongoClient(url)
except Exception as e:
    print(e)
    exit()

ul = uploader.MongoUploader(client, params["database"])
ul.upload_glucose(df, df_glucose_col="glucose", df_date_col="datetime", perform_test=False)

