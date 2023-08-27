import datetime
from typing import Callable, Optional

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


def decode_sql_error(
    exception: Exception,
    on_null: Callable[[Exception], Exception],
    on_duplicate: Callable[[Exception], Exception],
    fallback: Optional[Callable[[Exception], Exception]] = None,
    **kwargs
) -> Exception:

    """Analyze an exception for a SQL constraint violation

    Currently analyzes SQLAlchemy IntegrityException instances for NOT NULL and
    UNIQUE KEY constraints, constsructing and returning an appropriate
    exception. If the exception doesn't match a recognized SQL constraint,
    construct and return a fallback exception type if specified or the original
    exception.

    Args:
        exception: An exception to decode
        on_null: Exception class to build if null contraint
        on_duplicate: Exception class to build with if duplicate constraint
        fallback: Exception class to build otherwise
        kwargs: additional arguments passed to exception constructors

    Returns:
        a more specific exception, or the original if no matches are found and
        no fallback template is provided.
    """
    if isinstance(exception, IntegrityError):
        cause = exception.orig.args[-1].lower()
        if "unique constraint" in cause:
            return on_duplicate(exception, **kwargs)
        elif "not null constraint" in cause:
            return on_null(exception, **kwargs)
    return exception if not fallback else fallback(exception, **kwargs)
