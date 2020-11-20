import logging
import logging.handlers

from configparser import NoOptionError, NoSectionError
from datetime import datetime
from pathlib import Path

from pbench.common.exceptions import BadConfig


class _Message:
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
        self.converter = datetime.utcfromtimestamp

    def formatTime(self, record, datefmt=None):
        """
        Return the creation time of the specified LogRecord as formatted text.
        """
        return self.converter(record.created).isoformat()

    def format(self, record):
        # Included from Python's logging.Formatter and then altered slightly to
        # replace \n with #012
        record.message = record.getMessage()
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)
        msg = self.formatMessage(record).replace("\n", "#012")
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
        if record.stack_info:
            if not msg.endswith("#012"):
                msg = msg + "#012"
            msg = msg + self.formatStack(record.stack_info).replace("\n", "#012")
        if self.max_line_length > 0 and len(msg) > self.max_line_length:
            if self.max_line_length < 7:
                msg = msg[: self.max_line_length]
            else:
                approxhalf = (self.max_line_length - 5) // 2
                msg = msg[:approxhalf] + " ... " + msg[-approxhalf:]
        return msg


# Used to track the individual logging handlers created by callers of
# get_pbench_logger().
_handlers = {}

# Constant for the location of the FIFO used by the SysLogHandler when
# the "logger_type" "devlog" is specified.
_devlog = "/dev/log"


def get_pbench_logger(caller, config):
    """Fetch the logger specifed by "caller", and add a specific handler
    based on the logging configuration requested.

    We also return a logger that supports "brace" style message formatting,
    e.g. logger.warning("that = {}", that)
    """

    pbench_logger = logging.getLogger(caller)
    if caller not in _handlers:
        try:
            logging_level = config.get(caller, "logging_level")
        except (NoSectionError, NoOptionError):
            logging_level = config.default_logging_level
        pbench_logger.setLevel(logging_level)

        if config.logger_type == "file":
            log_dir = Path(config.log_dir)
            if config.log_using_caller_directory:
                log_dir = log_dir / caller
            try:
                log_dir.mkdir()
            except FileExistsError:
                # directory already exists, ignore
                pass
            handler = logging.FileHandler(log_dir / f"{caller}.log")
        elif config.logger_type == "devlog":
            handler = logging.handlers.SysLogHandler(address=_devlog)
        elif (
            config.logger_type == "hostport"
        ):  # hostport logger type uses UDP-based logging
            handler = logging.handlers.SysLogHandler(
                address=(config.logger_host, int(config.logger_port))
            )
        else:
            raise BadConfig("Unsupported logger type")

        handler.setLevel(logging.DEBUG)
        if config.log_fmt is None:
            logfmt = "{asctime} {levelname} {process} {thread} {name}.{module} {funcName} {lineno} -- {message}"
        else:
            logfmt = config.log_fmt
        formatter = _PbenchLogFormatter(fmt=logfmt)
        handler.setFormatter(formatter)
        _handlers[caller] = handler
        pbench_logger.addHandler(handler)
    return _StyleAdapter(pbench_logger)
