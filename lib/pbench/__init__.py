"""
Simple module level convenience functions.
"""

from configparser import ConfigParser, NoSectionError, NoOptionError

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
            self.default_logging_level = self.conf.get("logging", "logging_level")
        except (NoOptionError, NoSectionError):
            self.default_logging_level = "INFO"

        # Constants

        # Force UTC everywhere
        self.TZ = "UTC"

    def get(self, *args, **kwargs):
        return self.conf.get(*args, **kwargs)
