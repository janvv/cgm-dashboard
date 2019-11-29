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

    def update_entries(self, limit_days=0):
        """
        :param limit_days: int
            Number of days into the past to query cgm data for
        :return: List of tuples (timestamp (seconds), glucose value) or None if error occured
        """
        if limit_days < 0:
            raise AttributeError("num_days {} has to be positive")

        # identify existing data
        now = datetime.now()
        t_end = now.timestamp()
        t_start = 0 if limit_days == 0 else (now - timedelta(days=limit_days)).timestamp()
        datetime_latest_queried_item = self.latest_query_time

        fmt = "%Y-%m-%d %H:%i:%s"
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
                'the times are therefore always in UTC'
                'Any sort of manipulation (getting the hour) automatically is converted into local timezone'
                'Need to change to timezone aware objects to avoid inconsistencies'
                'i.e. local time of day will be different depending on timezone the data is processed in'
                temp_df = pd.DataFrame(data=tuples, columns=[DATETIME_COLUMN, GLUCOSE_COLUMN])
                self.df = self.df.append(temp_df, sort=False, ignore_index=True).drop_duplicates()

                '#ATM  we can not use the last item from the pandas dataframe because it '
                'gives a different timestamp, thus we are using the tuples directly'
                t, g = zip(*tuples)
                datetime_latest_queried_item = max(t).timestamp()


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

    def get_entries(self, n_days=14, update=True):
        start_datetime = (datetime.now()-timedelta(days=n_days))

        '#check if we need to update data'
        if update and (((datetime.now().timestamp()-self.latest_query_time) > 1*60) or (start_datetime.timestamp() < self.earlierst_query_time)):
            success = self.update_entries(n_days)
            if not success:
                return None

        sub_frame = self.df.loc[self.df[DATETIME_COLUMN] > start_datetime].sort_values(DATETIME_COLUMN)
        if len(sub_frame) > 0:
            return sub_frame
        else:
            return None

    def get_last_entry(self, update=False):
        df = self.get_entries(1, update=update)
        if df is not None:
            return df.loc[df[DATETIME_COLUMN].idxmax()]
        else:
            return None

    def get_current_day_entries(self, update=False):
        sub_frame = self.get_entries(1, update=update)
        if sub_frame is not None:
            to_date = datetime.now().date()
            groups = sub_frame.groupby(sub_frame[DATETIME_COLUMN].apply(lambda x: x.date()))
            if to_date in groups.groups:
                result = groups.get_group(to_date)
                return result
        return None

