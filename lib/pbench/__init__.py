"""
Simple module level convenience functions.
"""

from configparser import ConfigParser, NoSectionError, NoOptionError
from typing import NamedTuple

from pbench.common import configtools
from pbench.common.exceptions import BadConfig


# Standard normalized date/time format
_STD_DATETIME_FMT = "%Y-%m-%dT%H:%M:%S.%f"


class PbenchConfig:
    """A simple class to wrap a ConfigParser object using the configtools
    style of multiple configuration files.
    """

    def __init__(self, cfg_name):
        # Enumerate the list of files
        config_files = configtools.file_list(cfg_name)
        config_files.reverse()
        self.conf = ConfigParser()
        self.files = self.conf.read(config_files)

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
            self.log_dir = self.conf.get("logging", "log_dir")
        except (NoOptionError, NoSectionError):
            # Allow for compatibility with previous configuration files.  Any
            # sub-class of this base class can change the log directory as
            # necessary.  Note that this class ONLY records the value found in
            # the configuration file, it does not take any actions on it.
            self.log_dir = None

        # The Agent and Server classes behave a bit differently with respect
        # to logging when using the "file" logger type. While this is not
        # derived from a configuration file, we keep track of the behavioral
        # attribute with the configuration.  The sub-classes will override the
        # value as necessary.
        self.log_using_caller_directory = False

        try:
            self.default_logging_level = self.conf.get("logging", "logging_level")
        except (NoOptionError, NoSectionError):
            self.default_logging_level = "INFO"

        try:
            # We don't document the "log_format" parameter since it is really
            # only present to facilitate easier unit testing.
            self.log_fmt = self.conf.get("logging", "log_format")
        except (NoOptionError, NoSectionError):
            self.log_fmt = None

        # Constants

        # Force UTC everywhere
        self.TZ = "UTC"

    def get(self, *args, **kwargs):
        return self.conf.get(*args, **kwargs)


class PbenchNamedTuple(NamedTuple):
    """A simple extension of a NamedTuple to provide a deterministic string
    representation.
    """

    def __str__(self):
        """A string containing a deterministic representation of a NamedTuple

        Convert the field names to dict keys, produce them in sorted order, and
        render their object values.  For most field types, this is done in the
        usual way by Python.  In the case of object references, use the object's
        __str__() method if it has one other than the one inherited from the
        fundamental "object" (that prints the object's address, which varies
        from run to run).  For other objects, print out the object's class name.
        If anything goes wrong, produce a default value.
        """
        ret_val = {}
        for k, v in sorted(self._asdict().items()):
            try:
                if isinstance(
                    v, (dict, list, tuple, str, int, float, complex, bool, type(None))
                ):
                    ret_val[k] = v
                elif v.__class__.__str__ != object.__str__:
                    ret_val[k] = str(v)
                else:
                    ret_val[k] = f"<{v.__class__.__name__} object>"
            except Exception:
                ret_val[k] = "<unexpected thing>"
        return str(ret_val)
