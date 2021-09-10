from adapter import MongoAdapter, MongoAdapterSRV, RestAdapter, OfflineAdapter
from database import DataBase, DATETIME_COLUMN, GLUCOSE_COLUMN
from datetime import datetime, time, timedelta
from configparser import ConfigParser




#setup database and backend adapter
config = ConfigParser()
config.read('config.ini')
section = config.sections()[0]
if section == "MongoDB":
    adapter = MongoAdapter(config["MongoDB"])
if section == "MongoDB+SRV":
    adapter = MongoAdapterSRV(config[section])
elif section == "REST":
    adapter = RestAdapter(config["REST"])
elif section == "OFFLINE":
    adapter = OfflineAdapter()
else:
    exit()

x = adapter.query((datetime.now()-timedelta(days=7)).timestamp(), datetime.now().timestamp())
print(x)
