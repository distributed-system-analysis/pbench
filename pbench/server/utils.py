from datetime import datetime, tzinfo, timedelta
from time import time as _time


class simple_utc(tzinfo):
    def tzname(self, *args, **kwargs):
        return "UTC"

    def utcoffset(self, dt):
        return timedelta(0)

    def dst(self, dt):
        return timedelta(0)


def tstos(ts=None):
    if ts is None:
        ts = _time()
    dt = datetime.utcfromtimestamp(ts).replace(tzinfo=simple_utc())
    return dt.strftime("%Y-%m-%dT%H:%M:%S-%Z")
