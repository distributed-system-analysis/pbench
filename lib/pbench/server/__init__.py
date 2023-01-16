"""Server module level convenience functions."""

from configparser import NoOptionError, NoSectionError
from datetime import datetime, timedelta, tzinfo
from enum import auto, Enum
from logging import Logger
from pathlib import Path
from time import time as _time
from typing import Dict, List, Optional, Union

from pbench import PbenchConfig
from pbench.common.exceptions import BadConfig

# A type defined to conform to the semantic definition of a JSON structure
# with Python syntax.
JSONSTRING = str
JSONNUMBER = Union[int, float]
JSONVALUE = Union["JSONOBJECT", "JSONARRAY", JSONSTRING, JSONNUMBER, bool, None]
JSONARRAY = List[JSONVALUE]
JSONOBJECT = Dict[JSONSTRING, JSONVALUE]
JSON = JSONVALUE


class OperationCode(Enum):
    """Enumeration for CRUD operations.

    The standard CRUD REST API operations:

        CREATE: Instantiate a new resource
        READ:   Retrieve the state of a resource
        UPDATE: Modify the state of a resource
        DELETE: Remove a resource
    """

    CREATE = auto()
    READ = auto()
    UPDATE = auto()
    DELETE = auto()


class SimpleUTC(tzinfo):
    """TZ Info class to help create a UTC datetime object."""

    def tzname(self, *args, **kwargs) -> str:
        return "UTC"

    def utcoffset(self, dt) -> timedelta:
        return timedelta(0)

    def dst(self, dt) -> timedelta:
        return timedelta(0)


def tstos(ts: float = None) -> str:
    """Convert a floating point seconds from the Epoch into a string.

    Returns:
        A string representation of a datetime object with a UTC time zone.
    """
    if ts is None:
        ts = _time()
    dt = datetime.utcfromtimestamp(ts).replace(tzinfo=SimpleUTC())
    return dt.strftime("%Y-%m-%dT%H:%M:%S-%Z")


class PbenchServerConfig(PbenchConfig):
    """An encapsulation of the configuration for the Pbench Server."""

    # Set of required properties.
    REQ_PROPS = frozenset(
        (
            "TOP",
            "TMP",
            "LOGSDIR",
            "BINDIR",
            "LIBDIR",
            "ARCHIVE",
            "INCOMING",
            "RESULTS",
            "USERS",
        )
    )

    # Define a fallback default for dataset maximum retention, which we expect
    # to be defined in pbench-server-default.cfg.
    MAXIMUM_RETENTION_DAYS = 3650

    @classmethod
    def create(cls: "PbenchServerConfig", cfg_name: str) -> "PbenchServerConfig":
        """Construct a Pbench server configuration object and validate that all the
        required properties are present.

        Returns:
            A PbenchServerConfig instance.
        """
        sc = cls(cfg_name)

        # The following will reference all the required properties tripping a raise
        # of BadConfig if any of the properties are missing their base config value.
        req_props = [getattr(sc, attr) for attr in cls.REQ_PROPS]
        # The following assertion will always be True, but it keeps linters quiet.
        assert len(req_props) == len(cls.REQ_PROPS)

        return sc

    def __init__(self, cfg_name: str):
        """Constructor to add specific fields for the operation of the server.

        Args:
            cfg_name : The configuration file name to use
        """
        super().__init__(cfg_name)

        # The pbench server, unlike the pbench agent code, logs to separate
        # directories for each caller.
        self.log_using_caller_directory = True

        # Constants

        # Initial common timestamp format
        self.TS = f"run-{tstos(_time())}"

    @property
    def TOP(self) -> Path:
        return self._get_valid_dir_option("TOP", "pbench-server", "pbench-top-dir")

    @property
    def TMP(self) -> Path:
        return self._get_valid_dir_option("TMP", "pbench-server", "pbench-tmp-dir")

    @property
    def LOGSDIR(self) -> Path:
        if self.log_dir:
            # We have a logging directory, which means the logger_type is
            # "file", so we'll ignore any "pbench-logs-dir" configuration
            # values.
            return Path(self.log_dir)

        # We don't have a [logging] section "log_dir" option, so we'll
        # fetch the old "pbench-logs-dir" option.
        logsdir = self._get_valid_dir_option(
            "LOGSDIR", "pbench-server", "pbench-logs-dir"
        )
        # Provide a value for log_dir since it was provided via the old
        # pbench-logs-dir configuration.
        self.log_dir = str(logsdir)
        return logsdir

    @property
    def BINDIR(self) -> Path:
        return self._get_valid_dir_option("BINDIR", "pbench-server", "script-dir")

    @property
    def LIBDIR(self) -> Path:
        return self._get_valid_dir_option("LIBDIR", "pbench-server", "lib-dir")

    @property
    def ARCHIVE(self) -> Path:
        return self._get_valid_dir_option(
            "ARCHIVE", "pbench-server", "pbench-archive-dir"
        )

    @property
    def INCOMING(self) -> Path:
        return self.TOP / "public_html" / "incoming"

    @property
    def RESULTS(self) -> Path:
        # This is where the symlink forest is going to go.
        return self.TOP / "public_html" / "results"

    @property
    def USERS(self) -> Path:
        return self.TOP / "public_html" / "users"

    @property
    def PBENCH_ENV(self) -> str:
        return self.conf.get("pbench-server", "environment", fallback="")

    @property
    def COMMIT_ID(self) -> str:
        return self.conf.get("pbench-server", "commit_id", fallback="(unknown)")

    @property
    def rest_uri(self) -> str:
        return self._get_conf("pbench-server", "rest_uri")

    @property
    def max_retention_period(self) -> int:
        """Produce an integer representing the maximum number of days the server
        allows a dataset to be retained.

        Returns:
            integer representing retention period in days
        """
        try:
            retention_days = int(
                self._get_conf("pbench-server", "maximum-dataset-retention-days")
            )
        except (NoOptionError, NoSectionError):
            retention_days = self.MAXIMUM_RETENTION_DAYS
        return retention_days

    def _get_conf(self, section: str, option: str) -> str:
        """Get the option from the section.

        Args:
            section : The configuration section name to find the option
            option : The option name to find in the given section

        Raises:
            BadConfig : when the option is empty, the option is missing, or the
                section is missing

        Returns:
            The option value as a string.
        """
        try:
            option_val = self.conf.get(section, option)
        except (NoOptionError, NoSectionError) as exc:
            raise BadConfig(str(exc))
        else:
            if not option_val:
                raise BadConfig(f"option {option} in section {section} is empty")

        return option_val

    def get_conf(self, env_name: str, section: str, option: str, logger: Logger) -> str:
        """Get the option from the section.

        Args:
            env_name : Legacy environment name to display in error messages
            section : The configuration section name to find the option
            option : The option name to find in the given section
            logger : The logger to use when a bad configuration is encountered

        Returns:
            The option value as a string, if present, else None.
        """
        try:
            option_val = self._get_conf(section, option)
        except BadConfig as exc:
            logger.error("Bad {}= '({})'", env_name, exc)
            return None

        return option_val

    def _get_valid_dir_option(self, env_name: str, section: str, option: str) -> Path:
        """Get the validated directory option from the given section.

        Args:
            env_name : Legacy environment name to display in error messages
            section : The configuration section name to find the option
            option : The option name to find in the given section

        Raises:
            BadConfig : if the directory option does not resolve to a directory
                on the file system, or if the option is missing, or if the
                section is missing

        Returns:
            A Path directory object.
        """
        dir_val = self._get_conf(section, option)
        dir_path = self._get_valid_path(env_name, dir_val, None)
        if not dir_path:
            raise BadConfig(f"Bad {env_name}={dir_val}")

        return dir_path

    def _get_valid_path(
        self, env_name: str, dir_val: str, logger: Union[None, Logger]
    ) -> Optional[Path]:
        """Get the fully resolved path from the given path.

        If a logger is given, will emit error logs when the directory is not
        found or the resolved name is not a directory.

        Args:
            env_name : Legacy environment name to display in error messages
            dir_val : A directory value to resolve to a real directory
            logger : Logger to use when low-level error messages should be
                emitted

        Returns:
            A Path directory object of the directory on disk, None otherwise.
        """
        try:
            dir_path = Path(dir_val).resolve(strict=True)
        except FileNotFoundError:
            if logger:
                logger.error(
                    "The {} directory, '{}', does not resolve to a real location",
                    env_name,
                    dir_val,
                )
            return None
        else:
            if not dir_path.is_dir():
                if logger:
                    logger.error(
                        "The {} directory, does not resolve to a directory ('{}')",
                        env_name,
                        dir_path,
                    )
                return None
        return dir_path

    def get_valid_dir_option(
        self, env_name: str, dir_val: str, logger: Union[None, Logger]
    ) -> Optional[Path]:
        """Get the validated directory option from the given section.

        Args:
            env_name : Legacy environment name to display in error messages
            dir_val : A directory value to resolve to a real directory
            logger : Logger to use when low-level error messages should be
                emitted

        Returns:
            A Path directory object, None if the directory value does not
                resolve to a real directory.
        """
        dir_path = self._get_valid_path(env_name, dir_val, logger)
        if not dir_path:
            return None

        return dir_path

    def timestamp(self) -> str:
        """Generate a time stamp string.

        Returns:
            The current timestamp formatted as a string of the following form:
                <YYYY>-<MM>-<DD>T<hh>:<mm>:<ss>-<TZ>
        """
        return tstos(_time())
