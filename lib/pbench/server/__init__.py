"""
Simple module level convenience functions.
"""

from pathlib import Path
from datetime import datetime, tzinfo, timedelta
from time import time as _time
from configparser import NoSectionError, NoOptionError

from pbench import PbenchConfig, _STD_DATETIME_FMT
from pbench.common.exceptions import BadConfig


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


class PbenchServerConfig(PbenchConfig):
    """PbenchServerConfig - a sub-class of the PbenchConfig class specifically
    for the pbench server environment.
    """

    def __init__(self, cfg_name):
        super().__init__(cfg_name)

        # Now fetch some default common pbench settings that are required.
        try:
            self.TOP = Path(self.conf.get("pbench-server", "pbench-top-dir"))
            if not self.TOP.is_dir():
                raise BadConfig(f"Bad TOP={self.TOP}")
            self.TMP = Path(self.conf.get("pbench-server", "pbench-tmp-dir"))
            if not self.TMP.is_dir():
                raise BadConfig(f"Bad TMP={self.TMP}")
            self.LOGSDIR = Path(self.conf.get("pbench-server", "pbench-logs-dir"))
            if not self.LOGSDIR.is_dir():
                raise BadConfig(f"Bad LOGSDIR={self.LOGSDIR}")
            self.BINDIR = Path(self.conf.get("pbench-server", "script-dir"))
            if not self.BINDIR.is_dir():
                raise BadConfig(f"Bad BINDIR={self.BINDIR}")
            self.LIBDIR = Path(self.conf.get("pbench-server", "lib-dir"))
            if not self.LIBDIR.is_dir():
                raise BadConfig(f"Bad LIBDIR={self.LIBDIR}")
            # the scripts may use this to send status messages
            self.mail_recipients = self.conf.get("pbench-server", "mailto")
        except (NoOptionError, NoSectionError) as exc:
            raise BadConfig(str(exc))
        else:
            self.ARCHIVE = Path(self.conf.get("pbench-server", "pbench-archive-dir"))
            self.INCOMING = self.TOP / "public_html" / "incoming"
            # this is where the symlink forest is going to go
            self.RESULTS = self.TOP / "public_html" / "results"
            self.USERS = self.TOP / "public_html" / "users"

        try:
            self.PBENCH_ENV = self.conf.get("pbench-server", "environment")
        except NoOptionError:
            self.PBENCH_ENV = ""

        try:
            self.COMMIT_ID = self.conf.get("pbench-server", "commit_id")
        except NoOptionError:
            self.COMMIT_ID = "(unknown)"

        try:
            self._unittests = self.conf.get("pbench-server", "debug_unittest")
        except Exception:
            self._unittests = False
        else:
            self._unittests = bool(self._unittests)

        if self._unittests:

            def mocked_time():
                return 42.00

            global _time
            _time = mocked_time

            try:
                ref_dt_str = self.conf.get("pbench-server", "debug_ref_datetime")
            except Exception:
                ref_dt_str = "1970-01-02T00:00:00.000000"
            self._ref_datetime = datetime.strptime(ref_dt_str, _STD_DATETIME_FMT)
        else:
            self._ref_datetime = None

        # Constants

        # Initial common timestamp format
        self.TS = f"run-{self.timestamp()}"
        # Make all the state directories for the pipeline and any others
        # needed.  Every related state directories are paired together with
        # their final state at the end.
        self.LINKDIRS = (
            "TODO BAD-MD5"
            " TO-UNPACK UNPACKED WONT-UNPACK"
            " TO-SYNC SYNCED"
            " TO-LINK"
            " TO-INDEX TO-RE-INDEX TO-INDEX-TOOL INDEXED WONT-INDEX"
            " TO-COPY-SOS COPIED-SOS"
            " TO-BACKUP BACKED-UP BACKUP-FAILED"
            " SATELLITE-MD5-PASSED SATELLITE-MD5-FAILED"
            " TO-DELETE SATELLITE-DONE"
        )
        # List of the state directories which will be excluded during rsync.
        # Note that range(1,12) generates the sequence [1..11] inclusively.
        self.EXCLUDE_DIRS = (
            "_QUARANTINED "
            + self.LINKDIRS
            + " "
            + " ".join([f"WONT-INDEX.{i:d}" for i in range(1, 12)])
        )

    def timestamp(self):
        """
        "Return the current timestamp formatted as a string of the following form:
                  <YYYY>-<MM>-<DD>T<hh>:<mm>:<ss>-<TZ>
        """
        return tstos(_time())
