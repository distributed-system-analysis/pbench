import datetime

from sqlalchemy import DateTime
from sqlalchemy.exc import IntegrityError
from sqlalchemy.types import TypeDecorator


class TZDateTime(TypeDecorator):
    """Helper type decorator to ensure time stamps are consistent.

    SQLAlchemy protocol is that stored time stamps are naive UTC; so we use a
    custom type decorator to ensure that our incoming and outgoing timestamps
    are consistent by adjusting TZ before storage and enhancing with UTC TZ
    on retrieval so that we're always working with "aware" UTC.
    """

    impl = DateTime
    cache_ok = True

    @staticmethod
    def current_time() -> datetime.datetime:
        """Return the current time in UTC.

        This provides a Callable that can be specified in the SQLAlchemy Column
        to generate an appropriate (aware UTC) datetime object when a Dataset
        object is created.

        Returns:
            Current UTC timestamp
        """
        return datetime.datetime.now(datetime.timezone.utc)

    def process_bind_param(self, value, dialect):
        """Ensure use of "naive" datetime objects for storage.

        "Naive" datetime objects are treated as UTC, and "aware" datetime
        objects are converted to UTC and made "naive" by replacing the TZ
        for SQL storage.
        """
        if value is not None and value.utcoffset() is not None:
            value = value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        """Ensure use of "aware" datetime objects for API clients.

        Retrieved datetime objects are naive, and are assumed to be UTC, so set
        the TZ to UTC to make them "aware". This ensures that we communicate
        the "+00:00" ISO 8601 suffix to API clients.
        """
        if value is not None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value


class commonDBException(Exception):
    """Generic base class for reporting errors ."""

    def DuplicateValue(self):
        """This method will be invoked if SQLAlchemy IntegrityError
        throws UNIQUE constraint violation

        ABSTRACT METHOD: override in subclass to perform operation.
        """
        raise NotImplementedError()

    def NullKey(self):
        """This method will be invoked if SQLAlchemy IntegrityError
        throws NOT NULL constraint violation

        ABSTRACT METHOD: override in subclass to perform operation.
        """
        raise NotImplementedError()

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
        if "UNIQUE constraint" in cause:
            return self.DuplicateValue(self, cause)
        elif "NOT NULL constraint" in cause:
            return self.NullKey(self, cause)
        return exception
