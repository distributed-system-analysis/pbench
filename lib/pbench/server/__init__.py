"""
Simple module level convenience functions.
"""

from configparser import NoOptionError, NoSectionError
from datetime import datetime, timedelta, tzinfo
from pathlib import Path
from time import time as _time
from typing import Dict, List, Union

from pbench import _STD_DATETIME_FMT, PbenchConfig
from pbench.common.exceptions import BadConfig

# A type defined to conform to the semantic definition of a JSON structure
# with Python syntax.
JSONSTRING = str
JSONNUMBER = Union[int, float]
JSONVALUE = Union["JSONOBJECT", "JSONARRAY", JSONSTRING, JSONNUMBER, bool, None]
JSONARRAY = List[JSONVALUE]
JSONOBJECT = Dict[JSONSTRING, JSONVALUE]
JSON = JSONVALUE


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

    # Define a fallback default for dataset maximum retention, which we expect
    # to be defined in pbench-server-default.cfg.
    MAXIMUM_RETENTION_DAYS = 3650

    def __init__(self, cfg_name):
        super().__init__(cfg_name)

        # Now fetch some default common pbench settings that are required.
        self.TOP = self._get_valid_dir_option("TOP", "pbench-server", "pbench-top-dir")
        self.TMP = self._get_valid_dir_option("TMP", "pbench-server", "pbench-tmp-dir")
        if self.log_dir:
            # We have a logging directory, which means the logger_type is
            # "file", so we'll ignore any "pbench-logs-dir" configuration
            # values.
            self.LOGSDIR = Path(self.log_dir)
        else:
            # We don't have a [logging] section "log_dir" option, so we'll
            # fetch the old "pbench-logs-dir" option.
            self.LOGSDIR = self._get_valid_dir_option(
                "LOGSDIR", "pbench-server", "pbench-logs-dir"
            )
            # Provide a value for log_dir since it was provided via the old
            # pbench-logs-dir configuration.
            self.log_dir = str(self.LOGSDIR)
        # The pbench server, unlike the pbench agent code, logs to separate
        # directories for each caller.
        self.log_using_caller_directory = True
        self.BINDIR = self._get_valid_dir_option(
            "BINDIR", "pbench-server", "script-dir"
        )
        self.LIBDIR = self._get_valid_dir_option("LIBDIR", "pbench-server", "lib-dir")
        self.ARCHIVE = self._get_valid_dir_option(
            "ARCHIVE", "pbench-server", "pbench-archive-dir"
        )

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

        if self._unittests:

            def mocked_time():
                return 42.00

            global _time
            _time = mocked_time

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

    @property
    def server_config(self):
        return self.conf["pbench-server"]

    @property
    def mail_recipients(self):
        try:
            return self.conf.get("pbench-server", "mailto")
        except (NoOptionError, NoSectionError):
            return ""

    @property
    def _unittests(self):
        try:
            unittests = self.conf.get("pbench-server", "debug_unittest")
        except (NoOptionError, NoSectionError):
            return False
        else:
            return bool(unittests)

    @property
    def _ref_datetime(self):
        if self._unittests:
            try:
                ref_dt_str = self.conf.get("pbench-server", "debug_ref_datetime")
            except Exception:
                ref_dt_str = "1970-01-02T00:00:00.000000"
            return datetime.strptime(ref_dt_str, _STD_DATETIME_FMT)
        else:
            return None

    @property
    def rest_uri(self):
        return self._get_conf("pbench-server", "rest_uri")

    @property
    def max_retention_period(self) -> int:
        """
        Produce a timedelta representing the number of days the server allows
        a dataset to be retained.

        Returns
            delta time representing retention period
        """
        try:
            retention_days = int(
                self._get_conf("pbench-server", "maximum-dataset-retention-days")
            )
        except (NoOptionError, NoSectionError):
            retention_days = self.MAXIMUM_RETENTION_DAYS
        return retention_days

    def _get_conf(self, section, option):
        """
        _get_conf - get the option from the section, raising
        BadConfig Error if it is empty, return the option value as a string.
        """
        try:
            option_val = self.conf.get(section, option)
        except (NoOptionError, NoSectionError) as exc:
            raise BadConfig(str(exc))
        else:
            if not option_val:
                raise BadConfig(f"option {option} in section {section} is empty")

        return option_val

    def get_conf(self, name, section, option, logger):
        """
        get_conf - get the option from the section, raising BadConfig Error
        if it is empty, return the option value as a string.
        """
        try:
            option_val = self._get_conf(section, option)
        except BadConfig as exc:
            logger.error("Bad {}= '({})'", name, exc)
            return None

        return option_val

    def _get_valid_dir_option(self, req_val, section, option):
        """_get_valid_dir_option - get the directory option from the
        given section, raising BadConfig Error if the path is not resolved
        or is not a directory, returning a Path directory object.
        """
        dir_val = self._get_conf(section, option)
        dir_path = self._get_valid_path(req_val, dir_val, None)
        if not dir_path:
            raise BadConfig(f"Bad {req_val}={dir_val}")

        return dir_path

    def _get_valid_path(self, req_val, dir_val, logger):
        """_get_valid_path - get realpath from the given path, raising
        Error if the path is not resolved or is not a directory,
        returning a Path directory object.
        """
        try:
            dir_path = Path(dir_val).resolve(strict=True)
        except FileNotFoundError:
            if logger:
                logger.error(
                    "The {} directory, '{}', does not resolve to a real location",
                    req_val,
                    dir_val,
                )
            return None
        else:
            if not dir_path.is_dir():
                if logger:
                    logger.error(
                        "The {} directory, does not resolve to a directory ('{}')",
                        req_val,
                        dir_path,
                    )
                return None
        return dir_path

    def get_valid_dir_option(self, req_val, dir_val, logger):
        """get_valid_dir_option - get the directory path raising an Error
        if it is not a directory, returning a Path directory object.
        """
        dir_path = self._get_valid_path(req_val, dir_val, logger)
        if not dir_path:
            return None

        return dir_path

    def timestamp(self):
        """
        "Return the current timestamp formatted as a string of the following form:
                  <YYYY>-<MM>-<DD>T<hh>:<mm>:<ss>-<TZ>
        """
        return tstos(_time())
