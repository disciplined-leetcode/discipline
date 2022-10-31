import datetime
import sys
import os


def printException(e: Exception):
    """
    Print exception to stderr
    """
    print("Exception: ", e)
    print("Traceback: ", e.__traceback__)
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    print(exc_type, fname, exc_tb.tb_lineno)


def duration_till_next_day():
    day_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + datetime.timedelta(hours=24)
    return day_end - datetime.datetime.utcnow()
