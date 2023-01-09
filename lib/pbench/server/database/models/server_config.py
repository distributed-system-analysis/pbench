import re
from typing import Optional

from sqlalchemy import Column, Integer, String
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.sql.sqltypes import JSON

from pbench.server import JSONOBJECT, JSONVALUE
from pbench.server.database.database import Database


class ServerConfigError(Exception):
    """
    This is a base class for errors reported by the ServerConfig class. It is
    never raised directly, but may be used in "except" clauses.
    """

    pass


class ServerConfigSqlError(ServerConfigError):
    """
    SQLAlchemy errors reported through ServerConfig operations.

    The exception will identify the operation being performed and the config
    key; the cause will specify the original SQLAlchemy exception.
    """

    def __init__(self, operation: str, name: str, cause: str):
        self.operation = operation
        self.name = name
        self.cause = cause

    def __str__(self) -> str:
        return f"Error {self.operation} index {self.name!r}: {self.cause}"


class ServerConfigDuplicate(ServerConfigError):
    """
    Attempt to commit a duplicate ServerConfig.
    """

    def __init__(self, name: str, cause: str):
        self.name = name
        self.cause = cause

    def __str__(self) -> str:
        return f"Duplicate config setting {self.name!r}: {self.cause}"


class ServerConfigNullKey(ServerConfigError):
    """
    Attempt to commit a ServerConfig with an empty key.
    """

    def __init__(self, name: str, cause: str):
        self.name = name
        self.cause = cause

    def __str__(self) -> str:
        return f"Missing key value in {self.name!r}: {self.cause}"


class ServerConfigMissingKey(ServerConfigError):
    """
    Attempt to set a ServerConfig with an empty key.
    """

    def __str__(self) -> str:
        return "Missing key name"


class ServerConfigBadKey(ServerConfigError):
    """
    Attempt to commit a ServerConfig with a bad key.
    """

    def __init__(self, key: str):
        self.key = key

    def __str__(self) -> str:
        return f"Configuration key {self.key!r} is unknown"


class ServerConfigBadValue(ServerConfigError):
    """
    Attempt to assign a bad value to a server configuration option
    """

    def __init__(self, key: str, value: JSONVALUE):
        self.key = key
        self.value = value

    def __str__(self) -> str:
        return f"Unsupported value for configuration key {self.key!r} ({self.value!r})"


# Formal timedelta syntax is "[D day[s], ][H]H:MM:SS[.UUUUUU]"; without an
# external package we have no standard way to parse or format timedelta
# strings. Additionally for "lifetime" we don't care about fractional days,
# so we simpify by accepting "D[[ ]day[s]]".
_TIMEDELTA_FORMAT = re.compile(r"(?P<days>\d{1,9})(?:\s*days?)?")


def validate_lifetime(key: str, value: JSONVALUE) -> JSONVALUE:
    v = str(value)
    check = _TIMEDELTA_FORMAT.fullmatch(v)
    if check:
        days = check.group("days")
    else:
        raise ServerConfigBadValue(key, value)
    return days


# Define the minimum and maximum allowed length for a dataset name.
DATASET_NAME_LEN_MIN = "min"
DATASET_NAME_LEN_MAX = "max"


def validate_name_len(key: str, value: JSONVALUE) -> JSONVALUE:
    try:
        min = int(value[DATASET_NAME_LEN_MIN])
        max = int(value[DATASET_NAME_LEN_MAX])
    except (KeyError, TypeError, ValueError):
        raise ServerConfigBadValue(key, value)
    else:
        if min <= 0 or max < min or max > 1024:
            raise ServerConfigBadValue(key, value)
    return value


# Formal "state" syntax is a JSON object with a "status" key designating the
# current server status ("enabled", "disabled", or "readonly" to allow read
# access but not modification of resources), and a "message" string
# describing why the server isn't enabled. The "message" is required only if
# the "status" isn't "enabled". For example,
#
# {"status": "enabled"}
#
# or
#
# {"status": "disabled", "message": "Down for maintanance"}
#
# or
#
# {"status": "readonly", "message": "Available for queries but no changes allowed"}
#
# Additional fields can be set by an administrator and will be retained and
# reported when the state is queried or when an API call fails because the
# state isn't enabled.
STATE_STATUS_KEY = "status"
STATE_MESSAGE_KEY = "message"
STATE_STATUS_KEYWORD_DISABLED = "disabled"
STATE_STATUS_KEYWORD_ENABLED = "enabled"
STATE_STATUS_KEYWORD_READONLY = "readonly"
STATE_STATUS_KEYWORDS = [
    STATE_STATUS_KEYWORD_DISABLED,
    STATE_STATUS_KEYWORD_ENABLED,
    STATE_STATUS_KEYWORD_READONLY,
]


def validate_server_state(key: str, value: JSONVALUE) -> JSONVALUE:
    try:
        status = value[STATE_STATUS_KEY].lower()
    except (KeyError, SyntaxError, TypeError) as e:
        raise ServerConfigBadValue(key, value) from e
    if status not in STATE_STATUS_KEYWORDS:
        raise ServerConfigBadValue(key, value)

    # canonicalize the status value by lowercasing it
    value[STATE_STATUS_KEY] = status
    if status != STATE_STATUS_KEYWORD_ENABLED and STATE_MESSAGE_KEY not in value:
        raise ServerConfigBadValue(key, value)
    return value


# A set of string values, including a message for users that can be displayed
# as a banner in a client. This must include a "message" and may also include
# other fields such as administrator contacts, maintenance schedule.
BANNER_MESSAGE_KEY = "message"


def validate_server_banner(key: str, value: JSONVALUE) -> JSONVALUE:
    if not isinstance(value, dict) or BANNER_MESSAGE_KEY not in value:
        raise ServerConfigBadValue(key, value)
    return value


OPTION_DATASET_LIFETIME = "dataset-lifetime"
OPTION_DATASET_NAME_LEN = "dataset-name-len"
OPTION_SERVER_BANNER = "server-banner"
OPTION_SERVER_STATE = "server-state"

SERVER_CONFIGURATION_OPTIONS = {
    OPTION_DATASET_LIFETIME: {
        "validator": validate_lifetime,
        "default": lambda: str(ServerConfig.config.max_retention_period),
    },
    OPTION_DATASET_NAME_LEN: {
        "validator": validate_name_len,
        "default": lambda: {DATASET_NAME_LEN_MIN: 10, DATASET_NAME_LEN_MAX: 128},
    },
    OPTION_SERVER_BANNER: {
        "validator": validate_server_banner,
        "default": lambda: None,
    },
    OPTION_SERVER_STATE: {
        "validator": validate_server_state,
        "default": lambda: {STATE_STATUS_KEY: STATE_STATUS_KEYWORD_ENABLED},
    },
}


class ServerConfig(Database.Base):
    """
    A framework to manage Pbench configuration settings. This is a simple
    key-value store that can be used flexibly to manage runtime configuration.

    Columns:
        id      Generated unique ID of table row
        key     Configuration key name
        value   Configuration key value
    """

    KEYS = sorted([s for s in SERVER_CONFIGURATION_OPTIONS.keys()])

    __tablename__ = "serverconfig"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=True, index=True, nullable=False)
    value = Column(JSON, index=False, nullable=True)

    @staticmethod
    def _default(key: str) -> JSONVALUE:
        try:
            config = SERVER_CONFIGURATION_OPTIONS[key]
        except KeyError as e:
            if key:
                raise ServerConfigBadKey(key) from e
            else:
                raise ServerConfigMissingKey() from e
        return config["default"]()

    @staticmethod
    def _validate(key: str, value: JSONVALUE) -> JSONVALUE:
        try:
            config = SERVER_CONFIGURATION_OPTIONS[key]
        except KeyError as e:
            if key:
                raise ServerConfigBadKey(key) from e
            else:
                raise ServerConfigMissingKey() from e
        return config["validator"](key, value)

    @staticmethod
    def create(key: str, value: JSONVALUE) -> "ServerConfig":
        """
        A simple factory method to construct a new ServerConfig setting and
        add it to the database.

        Args:
            key: config setting key
            value: config setting value

        Returns:
            A new ServerConfig object initialized with the parameters and added
            to the database.
        """

        v = __class__._validate(key, value)
        config = ServerConfig(key=key, value=v)
        config.add()
        return config

    @staticmethod
    def get(key: str, use_default: bool = True) -> "ServerConfig":
        """
        Return a ServerConfig object with the specified configuration key
        setting. For example, ServerConfig.get("dataset-lifetime").

        If the setting has no definition, a default value will optionally
        be provided.

        Args:
            key: System configuration setting name
            use_default: If the DB value is None, return a default

        Raises:
            ServerConfigSqlError: problem interacting with Database

        Returns:
            ServerConfig object with the specified key name or None
        """
        try:
            config = Database.db_session.query(ServerConfig).filter_by(key=key).first()
            if config is None and use_default:
                config = ServerConfig(key=key, value=__class__._default(key))
        except SQLAlchemyError as e:
            raise ServerConfigSqlError("finding", key, str(e)) from e
        return config

    @staticmethod
    def set(key: str, value: JSONVALUE) -> "ServerConfig":
        """
        Update a ServerConfig key with the specified value. For
        example, ServerConfig.set("dataset-lifetime").

        Args:
            key: Configuration setting name

        Returns:
            ServerConfig object with the specified key name
        """

        v = __class__._validate(key, value)
        config = __class__.get(key, use_default=False)
        if config:
            config.value = v
            config.update()
        else:
            config = __class__.create(key=key, value=v)
        return config

    @staticmethod
    def get_disabled(readonly: bool = False) -> Optional[JSONOBJECT]:
        """
        Determine whether the current 'server-state' setting disallows the
        requested access. By default we check for WRITE access, which
        can be overridden by specifying 'readonly=True'

        Args:
            readonly: Caller requires only read access to the server API.

        Returns:
            None if the server is enabled. If the server is disabled for the
            requested access, the entire JSON value is returned and should be
            reported to a caller.
        """
        state = __class__.get(key=OPTION_SERVER_STATE)
        if state:
            value = state.value
            status = value[STATE_STATUS_KEY]
            if status == "disabled" or status == "readonly" and not readonly:
                return value
        return None

    @staticmethod
    def get_all() -> JSONOBJECT:
        """
        Return all server config settings as a JSON object
        """
        configs = Database.db_session.query(ServerConfig).all()
        db = {c.key: c.value for c in configs}
        return {k: db[k] if k in db else __class__._default(k) for k in __class__.KEYS}

    def __str__(self) -> str:
        """
        Return a string representation of the key-value pair

        Returns:
            string representation
        """
        return f"{self.key}: {self.value!r}"

    def _decode(self, exception: IntegrityError) -> Exception:
        """
        Decode a SQLAlchemy IntegrityError to look for a recognizable UNIQUE
        or NOT NULL constraint violation. Return the original exception if
        it doesn't match.

        Args:
            exception: An IntegrityError to decode

        Returns:
            a more specific exception, or the original if decoding fails
        """
        # Postgres engine returns (code, message) but sqlite3 engine only
        # returns (message); so always take the last element.
        cause = exception.orig.args[-1]
        if cause.find("UNIQUE constraint") != -1:
            return ServerConfigDuplicate(self.key, cause)
        elif cause.find("NOT NULL constraint") != -1:
            return ServerConfigNullKey(self.key, cause)
        return exception

    def add(self):
        """
        Add the ServerConfig object to the database
        """
        try:
            Database.db_session.add(self)
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            if isinstance(e, IntegrityError):
                raise self._decode(e) from e
            raise ServerConfigSqlError("adding", self.key, str(e)) from e

    def update(self):
        """
        Update the database row with the modified version of the
        ServerConfig object.
        """
        try:
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            if isinstance(e, IntegrityError):
                raise self._decode(e) from e
            raise ServerConfigSqlError("updating", self.key, str(e)) from e
