import logging
import pandas as pd
from datetime import datetime, timedelta, timezone

DATETIME_COLUMN = "datetime"
GLUCOSE_COLUMN = "glucose"


class DataBase:
    def __init__(self, adapter):

        self.logger = logging.getLogger(__name__)
        self.logger.info("Connecting to mongo db ...")
        self.earlierst_query_time = -1
        self.latest_query_time = -1
        self.df = pd.DataFrame(columns=[DATETIME_COLUMN, GLUCOSE_COLUMN])
        self.adapter = adapter

    def update_entries(self, start_datetime=None):
        """
        :param limit_days: int
            Number of days into the past to query cgm data for
        :return: List of tuples (timestamp (seconds), glucose value) or None if error occured
        """
        # identify existing data
        now = datetime.now()
        t_end = now.timestamp()
        t_start = 0 if start_datetime is None else start_datetime.timestamp()
        datetime_latest_queried_item = self.latest_query_time

        fmt = "%Y-%m-%d %H:%M:%S"
        self.logger.info("updating: {} - {}, existing: {} - {}".format(
            datetime.fromtimestamp(t_start).strftime(fmt),
            datetime.fromtimestamp(t_end).strftime(fmt),
            datetime.fromtimestamp(self.earlierst_query_time).strftime(fmt),
            datetime.fromtimestamp(self.latest_query_time).strftime(fmt)))

        # data before and after start of query range exists -> only search for missing data
        if (t_start > self.earlierst_query_time) and (t_start < self.latest_query_time):
            t_start = self.latest_query_time

        self.logger.info("querying: {} - {}".format(datetime.fromtimestamp(t_start).strftime(fmt),
                                                    datetime.fromtimestamp(t_end).strftime(fmt)))

        try:
            tuples = self.adapter.query(t_start, t_end)
            if len(tuples) > 0:
                self.logger.info("queried {} new entries".format(len(tuples)))

                '#Right now, the datetime objects are not carrying timezone information'
                temp_df = pd.DataFrame(data=tuples, columns=[DATETIME_COLUMN, GLUCOSE_COLUMN])
                self.df = self.df.append(temp_df, sort=False, ignore_index=True).drop_duplicates()

                'make sure to use .to_pydatetime() to calculate timestamp'
                'calling .timestamp() within pandas directly will wrongly give a wront timestamp' \
                'it wrongly uses the local time of the object as utc time' \
                'example: datetime object (10:00 local time (+1h)), pandas will give a timestamp +3600 seconds later ' \
                'which would be 10:00 in utc and 11:00 in local time'
                t, g = zip(*tuples)
                datetime_latest_queried_item = temp_df[DATETIME_COLUMN].max().to_pydatetime().timestamp() #utc
            else:
                self.logger.info("didn't find any new entries")


        except Exception as e:
            self.logger.error("Error while querying for last entries: \n {}".format(e))
            return False
        else:
            '#update query times (only if query returned results)'
            'we can not be sure that the database is fast enough to return values once they are imported'
            'therefore end-time is only updated if we received a new value'
            self.earlierst_query_time = min(t_start, self.earlierst_query_time) if (
                        self.earlierst_query_time != -1) else t_start
            self.latest_query_time = datetime_latest_queried_item
            return True

    def get_entries(self, start_datetime, update=True, reload=False):

        '#check if we need to update data'
        if reload or (update and (((datetime.now().timestamp()-self.latest_query_time) > 1*60) or (start_datetime.timestamp() < self.earlierst_query_time))):
            success = self.update_entries(start_datetime)
            if not success:
                return None

        sub_frame = self.df.loc[self.df[DATETIME_COLUMN] > start_datetime].sort_values(DATETIME_COLUMN)
        if len(sub_frame) > 0:
            return sub_frame.copy()
        else:
            return None

    def get_last_entry(self, update=False):
        self.update_entries(datetime.fromtimestamp(self.latest_query_time))
        return self.df.loc[self.df[DATETIME_COLUMN].idxmax()]

    def get_current_day_entries(self, update=False):
        date_today = datetime.now().date()
        datetime_start_of_today = datetime(year=date_today.year,
                                  month=date_today.month,
                                  day=date_today.day)

        sub_frame = self.get_entries(datetime_start_of_today, update=update)
        if sub_frame is not None:
            to_date = datetime.now().date()
            groups = sub_frame.groupby(sub_frame[DATETIME_COLUMN].apply(lambda x: x.date()))
            if to_date in groups.groups:
                result = groups.get_group(to_date)
                return result
        return None

