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
        self.TOP = self._get_valid_dir_option("TOP", "pbench-server", "pbench-top-dir")
        self.TMP = self._get_valid_dir_option("TMP", "pbench-server", "pbench-tmp-dir")
        self.LOGSDIR = self._get_valid_dir_option(
            "LOGSDIR", "pbench-server", "pbench-logs-dir"
        )
        self.BINDIR = self._get_valid_dir_option(
            "BINDIR", "pbench-server", "script-dir"
        )
        self.LIBDIR = self._get_valid_dir_option("LIBDIR", "pbench-server", "lib-dir")
        self.mail_recipients = self.conf.get("pbench-server", "mailto")
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

        try:
            self._unittests = self.conf.get("pbench-server", "debug_unittest")
        except Exception:
            self._unittests = False
        else:
            self._unittests = bool(self._unittests)

        try:
            self.elasticsearch = self.conf.get("elasticsearch", "server")
        except (NoOptionError, NoSectionError):
            self.elasticsearch = ""

        try:
            self.graphql = self.conf.get("graphql", "server")
        except (NoOptionError, NoSectionError):
            self.graphql = ""

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
