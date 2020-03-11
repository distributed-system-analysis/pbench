"""
Simple module level convenience functions.
"""

import os


from time import time as _time
from configparser import ConfigParser, NoSectionError, NoOptionError

from pbench.lib import configtools
from pbench.server import utils


class BadConfig(Exception):
    pass


class PbenchConfig(object):
    """A simple class to wrap a ConfigParser object using the configtools
       style of multiple configuration files.
    """

    def __init__(self, cfg_name):
        # Enumerate the list of files
        config_files = configtools.file_list(cfg_name)
        config_files.reverse()
        self.conf = ConfigParser()
        self.files = self.conf.read(config_files)

        # Now fetch some default common pbench settings that are required.
        try:
            self.TOP = self.conf.get("pbench-server", "pbench-top-dir")
            if not os.path.isdir(self.TOP):
                raise BadConfig("Bad TOP={}".format(self.TOP))
            self.TMP = self.conf.get("pbench-server", "pbench-tmp-dir")
            if not os.path.isdir(self.TMP):
                raise BadConfig("Bad TMP={}".format(self.TMP))
            self.LOGSDIR = self.conf.get("pbench-server", "pbench-logs-dir")
            if not os.path.isdir(self.LOGSDIR):
                raise BadConfig("Bad LOGSDIR={}".format(self.LOGSDIR))
            self.BINDIR = self.conf.get("pbench-server", "script-dir")
            if not os.path.isdir(self.BINDIR):
                raise BadConfig("Bad BINDIR={}".format(self.BINDIR))
            self.LIBDIR = self.conf.get("pbench-server", "lib-dir")
            if not os.path.isdir(self.LIBDIR):
                raise BadConfig("Bad LIBDIR={}".format(self.LIBDIR))
            # the scripts may use this to send status messages
            self.mail_recipients = self.conf.get("pbench-server", "mailto")
        except (NoOptionError, NoSectionError) as exc:
            raise BadConfig(str(exc))
        else:
            self.ARCHIVE = self.conf.get("pbench-server", "pbench-archive-dir")
            self.INCOMING = os.path.join(self.TOP, "public_html", "incoming")
            # this is where the symlink forest is going to go
            self.RESULTS = os.path.join(self.TOP, "public_html", "results")
            self.USERS = os.path.join(self.TOP, "public_html", "users")

        try:
            self.PBENCH_ENV = self.conf.get("pbench-server", "environment")
        except NoOptionError:
            self.PBENCH_ENV = ""

        try:
            self.COMMIT_ID = self.conf.get("pbench-server", "commit_id")
        except NoOptionError:
            self.COMMIT_ID = "(unknown)"

        try:
            self.logger_type = self.conf.get("logging", "logger_type")
        except (NoOptionError, NoSectionError):
            self.logger_type = "devlog"
        else:
            if self.logger_type == "hostport":
                try:
                    self.logger_host = self.conf.get("logging", "logger_host")
                    self.logger_port = self.conf.get("logging", "logger_port")
                except (NoOptionError) as exc:
                    raise BadConfig(str(exc))

        try:
            self._unittests = self.conf.get("pbench-server", "debug_unittest")
        except Exception as e:
            self._unittests = False
        else:
            self._unittests = bool(self._unittests)

        if self._unittests:

            def mocked_time():
                return 0

            global _time
            _time = mocked_time

        # Constants

        # Force UTC everywhere
        self.TZ = "UTC"
        # Initial common timestamp format
        self.TS = "run-{}".format(self.timestamp())
        # Make all the state directories for the pipeline and any others
        # needed.  Every related state directories are paired together with
        # their final state at the end.
        self.LINKDIRS = (
            "TODO BAD-MD5"
            " TO-UNPACK UNPACKED WONT-UNPACK"
            " TO-SYNC SYNCED"
            " TO-LINK"
            " TO-INDEX TO-INDEX-TOOL INDEXED WONT-INDEX"
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
            + " ".join(["WONT-INDEX.{:d}".format(i) for i in range(1, 12)])
        )

    def get(self, *args, **kwargs):
        return self.conf.get(*args, **kwargs)

    def timestamp(self):
        """
        "Return the current timestamp formatted as a string of the following form:
                  <YYYY>-<MM>-<DD>T<hh>:<mm>:<ss>-<TZ>
        """
        return utils.tstos(_time())
