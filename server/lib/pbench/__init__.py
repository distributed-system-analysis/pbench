"""
Simple module level convenience functions.
"""

import hashlib
import logging
import os
import shutil
import sys
from configparser import ConfigParser, NoOptionError, NoSectionError
from datetime import datetime, timedelta, tzinfo
from functools import partial
from logging import handlers
from pathlib import Path
from time import time as _time
from typing import Optional

import configtools

# On-disk tar ball file name pattern strings.
TAR_BALL_NAME_PAT_S = (
    r"\S+_(\d\d\d\d)[._-](\d\d)[._-](\d\d)[T_](\d\d)[._:](\d\d)[._:](\d\d)"
)
TAR_BALL_NAME_W_TAR_PAT_S = TAR_BALL_NAME_PAT_S + r"\.tar\.xz"
TAR_BALL_NAME_W_MD5_PAT_S = TAR_BALL_NAME_W_TAR_PAT_S + r"\.md5"

# Standard normalized date/time format
_STD_DATETIME_FMT = "%Y-%m-%dT%H:%M:%S.%f"


class simple_utc(tzinfo):
    def tzname(self, *args, **kwargs):
        return "UTC"

    def utcoffset(self, dt):
        return timedelta(0)

    def dst(self, dt):
        return timedelta(0)


UTC = simple_utc()


def utcnow():
    return datetime.utcfromtimestamp(_time()).replace(tzinfo=UTC)


def tstos(ts=None):
    if ts is None:
        ts = _time()
    dt = datetime.utcfromtimestamp(ts).replace(tzinfo=UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S-%Z")


class _Message(object):
    """An object that stores a format string, expected to be using the
    "brace" style formatting, and the arguments object which will be used
    to satisfy the formats.

    This allows for a delay in the formatting of the final logging
    message string to a point when the log message will actually be
    emitted.

    Taken from the Python Logging Cookbook, https://docs.python.org/3.6/howto/logging-cookbook.html#use-of-alternative-formatting-styles.
    """

    def __init__(self, fmt, args):
        self.fmt = fmt
        self.args = args

    def __str__(self):
        return self.fmt.format(*self.args)


class _StyleAdapter(logging.LoggerAdapter):
    """Wrap a python logger object with a logging.LoggerAdapter that uses
    the _Message() object so that log messages will be formatted using
    "brace" style formatting.

    Taken from the Python Logging Cookbook, https://docs.python.org/3.6/howto/logging-cookbook.html#use-of-alternative-formatting-styles.
    """

    def __init__(self, logger, extra=None):
        super().__init__(logger, extra or {})

    def log(self, level, msg, *args, **kwargs):
        if self.isEnabledFor(level):
            msg, kwargs = self.process(msg, kwargs)
            self.logger._log(level, _Message(msg, args), (), **kwargs)


class _PbenchLogFormatter(logging.Formatter):
    """Custom logging.Formatter for pbench server processes / environments.

    The pbench log formatter provides ISO timestamps in the log messages,
    formatting using "brace" style string formats by default, removal of
    new line ASCII characters (replaced with "#012"), optional max line
    length handling (broken in half with an elipsis between the halves).

    This work was originally copied from:

        https://github.com/openstack/swift/blob/1d4249ee9d176d5563631521fb17aa24baf7fbf3/swift/common/utils.py

    The original license is Apache 2.0 (see below).  See the associated
    LICENSE.log_formatter, and AUTHORS.log_formatter files in the code
    base.
    ---
    Copyright (c) 2010-2012 OpenStack Foundation

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
    implied.

    See the License for the specific language governing permissions and
    limitations under the License.
    """

    def __init__(self, fmt=None, datefmt=None, style="{", max_line_length=0):
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)
        self.max_line_length = max_line_length

    def format(self, record):
        # Included from Python's logging.Formatter and then altered slightly to
        # replace \n with #012
        record.message = record.getMessage()
        if self._fmt.find("{asctime}") >= 0:
            try:
                record.asctime = datetime.utcfromtimestamp(record.asctime).isoformat()
            except AttributeError:
                record.asctime = datetime.now().isoformat()
        msg = (self._fmt.format(**record.__dict__)).replace("\n", "#012")
        if record.exc_info:
            # Cache the traceback text to avoid converting it multiple times
            # (it's constant anyway)
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info).replace(
                    "\n", "#012"
                )
        if record.exc_text:
            if not msg.endswith("#012"):
                msg = msg + "#012"
            msg = msg + record.exc_text
        if self.max_line_length > 0 and len(msg) > self.max_line_length:
            if self.max_line_length < 7:
                msg = msg[: self.max_line_length]
            else:
                approxhalf = (self.max_line_length - 5) // 2
                msg = msg[:approxhalf] + " ... " + msg[-approxhalf:]
        return msg


# Used to track the individual FileHandler's created by callers of
# get_pbench_logger().
_handlers = {}


def get_pbench_logger(caller, config):
    """Add a specific handler for the caller using the configured LOGSDIR.

    We also return a logger that supports "brace" style message formatting,
    e.g. logger.warning("that = {}", that)
    """

    pbench_logger = logging.getLogger(caller)
    if caller not in _handlers:
        pbench_logger.setLevel(logging.DEBUG)
        logdir = os.path.join(config.LOGSDIR, caller)
        try:
            os.mkdir(logdir)
        except FileExistsError:
            # directory already exists, ignore
            pass

        if config.logger_type == "file":
            handler = logging.FileHandler(os.path.join(logdir, "{}.log".format(caller)))
        elif config.logger_type == "devlog":
            handler = handlers.SysLogHandler(address="/dev/log")
            handler.ident = f"{caller}: "
        elif (
            config.logger_type == "hostport"
        ):  # hostport logger type uses UDP-based logging
            handler = handlers.SysLogHandler(
                address=(config.logger_host, int(config.logger_port))
            )
            handler.ident = f"{caller}: "
        else:
            raise Exception("Unsupported logger type")

        handler.setLevel(logging.DEBUG)
        if not config._unittests:
            logfmt = "{asctime} {levelname} {process} {thread} {name}.{module} {funcName} {lineno} -- {message}"
        else:
            logfmt = "1970-01-01T00:00:42.000000 {levelname} {name}.{module} {funcName} -- {message}"
        formatter = _PbenchLogFormatter(fmt=logfmt)
        handler.setFormatter(formatter)
        _handlers[caller] = handler
        pbench_logger.addHandler(handler)
    return _StyleAdapter(pbench_logger)


class BadConfig(Exception):
    pass


class PbenchConfig(object):
    """A simple class to wrap a ConfigParser object using the configtools style
    of multiple configuration files.
    """

    # These fields are `export`d for `bash` command environments.
    export_list = frozenset(
        (
            "BINDIR",
            "COMMIT_ID",
            "INCOMING",
            "LIBDIR",
            "LOGSDIR",
            "PBENCH_ENV",
            "RESULTS",
            "TMP",
            "TOP",
            "TS",
            "TZ",
            "USERS",
        )
    )

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
                raise BadConfig("Bad TOP={}".format(self.TOP))  # noqa:E701
            self.TMP = self.conf.get("pbench-server", "pbench-tmp-dir")
            if not os.path.isdir(self.TMP):
                raise BadConfig("Bad TMP={}".format(self.TMP))  # noqa:E701
            self.LOGSDIR = self.conf.get("pbench-server", "pbench-logs-dir")
            if not os.path.isdir(self.LOGSDIR):
                raise BadConfig("Bad LOGSDIR={}".format(self.LOGSDIR))  # noqa:E701
            self.BINDIR = self.conf.get("pbench-server", "script-dir")
            if not os.path.isdir(self.BINDIR):
                raise BadConfig("Bad BINDIR={}".format(self.BINDIR))  # noqa:E701
            self.LIBDIR = self.conf.get("pbench-server", "lib-dir")
            if not os.path.isdir(self.LIBDIR):
                raise BadConfig("Bad LIBDIR={}".format(self.LIBDIR))  # noqa:E701
            # Cronjobs use this value for the MAILTO setting, ensure we have it
            # in the configuration.
            self.conf.get("pbench-server", "mailto")
        except (NoOptionError, NoSectionError) as exc:
            raise BadConfig(str(exc))
        else:
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
        except Exception:
            self._unittests = False
        else:
            self._unittests = bool(self._unittests)

        if self._unittests:
            try:
                clock_start = float(self.conf.get("pbench-server", "debug_clock_start"))
            except Exception:
                clock_start = 42.00

            def mocked_time():
                return clock_start

            global _time
            _time = mocked_time

        # Constants

        # Force UTC everywhere
        self.TZ = "UTC"
        # Initial common timestamp format
        self.TS = "run-{}".format(self.timestamp())

    def get(self, *args, **kwargs):
        return self.conf.get(*args, **kwargs)

    def timestamp(self):
        """
        "Return the current timestamp formatted as a string of the following form:
                  <YYYY>-<MM>-<DD>T<hh>:<mm>:<ss>-<TZ>
        """
        return tstos(_time())


def get_conf_dir(prog: str, config: PbenchConfig, option: str) -> Optional[Path]:
    """Convenience method to return a Path object for a resolved directory for
    the given option in the "pbench-server" section.

    Args:
        prog : The program name to display in error messages
        config : The pbench configuration object to consult
        option : The name of the option in the "pbench-server" section

    Returns:
        None on error, having printed a message to stderr, and a Path object
        to a fully resolved directory on success
    """
    option_val = config.conf.get("pbench-server", option)
    try:
        option_p = Path(option_val).resolve(strict=True)
    except Exception as e:
        print(
            f"{prog}: ERROR: could not resolve the configured"
            f" {option} directory, {option_val}: {e}",
            file=sys.stderr,
        )
        return None
    if not option_p.is_dir():
        print(
            f"{prog}: ERROR: The configured {option} directory,"
            f" {option_val}, is not a valid directory",
            file=sys.stderr,
        )
        return None
    return option_p


def md5sum(filename):
    """
    Return the MD5 check-sum of a given file.
    We don't want to read the entire file into memory.
    """
    with open(filename, mode="rb") as f:
        d = hashlib.md5()
        for buf in iter(partial(f.read, 128), b""):
            d.update(buf)
    return d.hexdigest()


def rename_tb_link(tb, dest, logger):
    try:
        os.mkdir(dest)
    except FileExistsError:
        # directory already exists, ignore
        pass
    except Exception:
        logger.exception(
            "os.mkdir: Unable to create tar ball destination directory: {}".format(dest)
        )
        raise
    tbname = os.path.basename(tb)
    tbnewname = os.path.join(dest, tbname)
    try:
        os.rename(tb, tbnewname)
    except Exception:
        logger.exception(
            "os.rename: Unable to move tar ball link {} to destination directory: {}".format(
                tb, dest
            )
        )
        raise


def quarantine(dest, logger, *files):
    """Quarantine problematic tarballs.
    Errors here are fatal but we log an error message to help diagnose
    problems.
    """
    try:
        os.mkdir(dest)
    except FileExistsError:
        # directory already exists, ignore
        pass
    except Exception:
        logger.exception('quarantine {} {!r}: "mkdir -p {}/" failed', dest, files, dest)
        sys.exit(101)

    for afile in files:
        if not os.path.exists(afile) and not os.path.islink(afile):
            continue
        try:
            shutil.move(afile, os.path.join(dest, os.path.basename(afile)))
        except Exception:
            logger.exception(
                'quarantine {} {!r}: "mv {} {}/" failed', dest, files, afile, dest
            )
            sys.exit(102)
