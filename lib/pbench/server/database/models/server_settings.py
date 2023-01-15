"""A framework to manage Pbench configuration settings."""
import re
from typing import Optional

from sqlalchemy import Column, Integer, String
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.sql.sqltypes import JSON

from pbench.server import JSONOBJECT, JSONVALUE
from pbench.server.database.database import Database


class ServerSettingError(Exception):
    """A base class for errors reported by the ServerSetting class.

    It is never raised directly, but may be used in "except" clauses.
    """


class ServerSettingSqlError(ServerSettingError):
    """SQLAlchemy errors reported through ServerSetting operations.

    The exception will identify the operation being performed and the setting
    key; the cause will specify the original SQLAlchemy exception.
    """

    def __init__(self, operation: str, name: str, cause: str):
        self.operation = operation
        self.name = name
        self.cause = cause

    def __str__(self) -> str:
        return f"Error {self.operation} index {self.name!r}: {self.cause}"


class ServerSettingDuplicate(ServerSettingError):
    """Attempt to commit a duplicate ServerSetting."""

    def __init__(self, name: str, cause: str):
        self.name = name
        self.cause = cause

    def __str__(self) -> str:
        return f"Duplicate server setting {self.name!r}: {self.cause}"


class ServerSettingNullKey(ServerSettingError):
    """Attempt to commit a ServerSetting with an empty key."""

    def __init__(self, name: str, cause: str):
        self.name = name
        self.cause = cause

    def __str__(self) -> str:
        return f"Missing key value in {self.name!r}: {self.cause}"


class ServerSettingMissingKey(ServerSettingError):
    """Attempt to set a ServerSetting with a missing key."""

    def __str__(self) -> str:
        return "Missing server setting key name"


class ServerSettingBadKey(ServerSettingError):
    """Attempt to commit a ServerSetting with a bad key."""

    def __init__(self, key: str):
        self.key = key

    def __str__(self) -> str:
        return f"Server setting key {self.key!r} is unknown"


class ServerSettingBadValue(ServerSettingError):
    """Attempt to assign a bad value to a server setting option."""

    def __init__(self, key: str, value: JSONVALUE):
        self.key = key
        self.value = value

    def __str__(self) -> str:
        return (
            f"Unsupported value for server settings key {self.key!r} ({self.value!r})"
        )


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
        raise ServerSettingBadValue(key, value)
    return days


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
        raise ServerSettingBadValue(key, value) from e
    if status not in STATE_STATUS_KEYWORDS:
        raise ServerSettingBadValue(key, value)

    # canonicalize the status value by lowercasing it
    value[STATE_STATUS_KEY] = status
    if status != STATE_STATUS_KEYWORD_ENABLED and STATE_MESSAGE_KEY not in value:
        raise ServerSettingBadValue(key, value)
    return value


# A set of string values, including a message for users that can be displayed
# as a banner in a client. This must include a "message" and may also include
# other fields such as administrator contacts, maintenance schedule.
BANNER_MESSAGE_KEY = "message"


def validate_server_banner(key: str, value: JSONVALUE) -> JSONVALUE:
    if not isinstance(value, dict) or BANNER_MESSAGE_KEY not in value:
        raise ServerSettingBadValue(key, value)
    return value


OPTION_DATASET_LIFETIME = "dataset-lifetime"
OPTION_SERVER_BANNER = "server-banner"
OPTION_SERVER_STATE = "server-state"

SERVER_SETTINGS_OPTIONS = {
    OPTION_DATASET_LIFETIME: {
        "validator": validate_lifetime,
        "default": lambda: str(ServerSetting.config.max_retention_period),
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


class ServerSetting(Database.Base):
    """A simple key-value store used to manage runtime settings.

    Columns:
        id      Generated unique ID of table row
        key     Setting key name
        value   Setting key value
    """

    KEYS = sorted([s for s in SERVER_SETTINGS_OPTIONS.keys()])

    __tablename__ = "server_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=True, index=True, nullable=False)
    value = Column(JSON, index=False, nullable=True)

    @staticmethod
    def _default(key: str) -> JSONVALUE:
        try:
            setting = SERVER_SETTINGS_OPTIONS[key]
        except KeyError as e:
            if key:
                raise ServerSettingBadKey(key) from e
            else:
                raise ServerSettingMissingKey() from e
        return setting["default"]()

    @staticmethod
    def _validate(key: str, value: JSONVALUE) -> JSONVALUE:
        try:
            setting = SERVER_SETTINGS_OPTIONS[key]
        except KeyError as e:
            if key:
                raise ServerSettingBadKey(key) from e
            else:
                raise ServerSettingMissingKey() from e
        return setting["validator"](key, value)

    @staticmethod
    def create(key: str, value: JSONVALUE) -> "ServerSetting":
        """A simple factory method to construct a new ServerSetting setting and
        add it to the database.

        Args:
            key : server setting key
            value : server setting value

        Returns:
            A new ServerSetting object initialized with the settings and added
            to the database.
        """

        v = __class__._validate(key, value)
        setting = ServerSetting(key=key, value=v)
        setting.add()
        return setting

    @staticmethod
    def get(key: str, use_default: bool = True) -> "ServerSetting":
        """Return a ServerSetting object with the specified key setting.

        For example, ServerSetting.get("dataset-lifetime").

        If the setting has no definition, a default value will optionally
        be provided.

        Args:
            key : System setting name
            use_default : If the DB value is None, return a default

        Raises:
            ServerSettingSqlError : problem interacting with Database

        Returns:
            ServerSetting object with the specified key name or None
        """
        try:
            setting = (
                Database.db_session.query(ServerSetting).filter_by(key=key).first()
            )
            if setting is None and use_default:
                setting = ServerSetting(key=key, value=__class__._default(key))
        except SQLAlchemyError as e:
            raise ServerSettingSqlError("finding", key, str(e)) from e
        return setting

    @staticmethod
    def set(key: str, value: JSONVALUE) -> "ServerSetting":
        """Update a ServerSetting key with the specified value.

        For example, ServerSetting.set("dataset-lifetime").

        Args:
            key : Configuration setting name

        Returns:
            ServerSetting object with the specified key name
        """
        v = __class__._validate(key, value)
        setting = __class__.get(key, use_default=False)
        if setting:
            setting.value = v
            setting.update()
        else:
            setting = __class__.create(key=key, value=v)
        return setting

    @staticmethod
    def get_disabled(readonly: bool = False) -> Optional[JSONOBJECT]:
        """Determine whether the current 'server-state' setting disallows the
        requested access.

        By default we check for WRITE access, which can be overridden by
        specifying 'readonly=True'

        Args:
            readonly : Caller requires only read access to the server API.

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
        """Return all server settings as a JSON object."""
        settings = Database.db_session.query(ServerSetting).all()
        db = {c.key: c.value for c in settings}
        return {k: db[k] if k in db else __class__._default(k) for k in __class__.KEYS}

    def __str__(self) -> str:
        """Return a string representation of the key-value pair.

        Returns:
            string representation
        """
        return f"{self.key}: {self.value!r}"

    def _decode(self, exception: IntegrityError) -> Exception:
        """Decode a SQLAlchemy IntegrityError to look for a recognizable UNIQUE
        or NOT NULL constraint violation.

        Return the original exception if it doesn't match.

        Args:
            exception : An IntegrityError to decode

        Returns:
            a more specific exception, or the original if decoding fails
        """
        # Postgres engine returns (code, message) but sqlite3 engine only
        # returns (message); so always take the last element.
        cause = exception.orig.args[-1]
        if cause.find("UNIQUE constraint") != -1:
            return ServerSettingDuplicate(self.key, cause)
        elif cause.find("NOT NULL constraint") != -1:
            return ServerSettingNullKey(self.key, cause)
        return exception

    def add(self):
        """Add the ServerSetting object to the database."""
        try:
            Database.db_session.add(self)
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            if isinstance(e, IntegrityError):
                raise self._decode(e) from e
            raise ServerSettingSqlError("adding", self.key, str(e)) from e

    def update(self):
        """Update the database row with the modified version of the
        ServerSetting object.
        """
        try:
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            if isinstance(e, IntegrityError):
                raise self._decode(e) from e
            raise ServerSettingSqlError("updating", self.key, str(e)) from e
