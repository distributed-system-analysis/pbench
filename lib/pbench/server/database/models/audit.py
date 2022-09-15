from datetime import datetime
import enum
from typing import Optional

from sqlalchemy import Column, Enum, Integer, String
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.sql.sqltypes import JSON

from pbench.server import JSONOBJECT, OperationCode
from pbench.server.database.database import Database
from pbench.server.database.models import TZDateTime
from pbench.server.database.models.datasets import Dataset
from pbench.server.database.models.users import User


class AuditError(Exception):
    """
    This is a base class for errors reported by the Audit class. It is
    never raised directly, but may be used in "except" clauses.
    """

    pass


class AuditSqlError(AuditError):
    """
    SQLAlchemy errors reported through Audit operations.

    The exception will identify the operation being performed and the config
    key; the cause will specify the original SQLAlchemy exception.
    """

    def __init__(self, operation: str, params: JSONOBJECT, cause: str):
        self.operation = operation
        self.params = params
        self.cause = cause

    def __str__(self) -> str:
        return f"Error {self.operation} {self.params!r}: {self.cause}"


class AuditDuplicate(AuditError):
    """
    Attempt to commit a duplicate ServerConfig.
    """

    def __init__(self, name: str, cause: str):
        self.name = name
        self.cause = cause

    def __str__(self) -> str:
        return f"Duplicate config setting {self.name!r}: {self.cause}"


class AuditNullKey(AuditError):
    """
    Attempt to commit a ServerConfig with an empty key.
    """

    def __init__(self, name: str, cause: str):
        self.name = name
        self.cause = cause

    def __str__(self) -> str:
        return f"Missing key value in {self.name!r}: {self.cause}"


class AuditType(enum.Enum):
    """
    The type of Pbench Server resource affected by a CREATE, UPDATE, or DELETE
    operation.
    """

    """Operation on a Dataset resource. This should include both the
    object_id and object_name."""
    DATASET = enum.auto()

    """Operation on a system configuration setting. There's no meaningful id
    or name; the 'attributes' column will record the actual attributes we
    set."""
    CONFIG = enum.auto()

    """A default when no resource is affected"""
    NONE = enum.auto()

    """An Elasticsearch template. The base template name will be recorded in
    object_name."""
    TEMPLATE = enum.auto()

    """Operation on an API token. There's no meaningful id or name."""
    TOKEN = enum.auto()


class AuditStatus(enum.Enum):

    """Pending operation: this signals the beginning of an optation that might
    fail or require further context later."""

    BEGIN = enum.auto()

    """Successful operation: an operation completed without problems."""
    SUCCESS = enum.auto()

    """Failed operation: an operation failed for reasons categorized by
    AuditReason and possibly further detailed by a message."""
    FAILURE = enum.auto()

    """Warning: the operation didn't fail, but wasn't able to complete with
    total success."""
    WARNING = enum.auto()


class AuditReason(enum.Enum):

    """Permission denied."""

    PERMISSION = enum.auto()

    """Internal failure."""
    INTERNAL = enum.auto()

    """Consistency failure. For example, a corrupted tarball upload."""
    CONSISTENCY = enum.auto()


class Audit(Database.Base):
    """
    A framework to store Pbench audit records. These will track server
    configuration changes as well as every mutation of user-visible data and
    attribute each to a specific user and operation.

    Architecturally, the SQL table may be used as a "front end" for a more
    expensive audit repository (e.g., Elasticsearch). For example, we might
    periodically bulk-replicate these rows as JSON data into an Elasticsearch
    index and wipe the table.

    Columns:
        id: Generated unique ID of table row
        root_id: Reference to the id of the operation's BEGIN audit record to
            enable following an operation with multiple records.
        name: Provide an optional name for the operation, like "upload" or
            "index".
        operation: The operation performed
        object_type: The type of resource
        object_id: The object on which an operation was performed
        object_name: The name of the object (more meaningful than ID if the
            resource has been deleted)
        user_id: The identity of the user performing an operation
        user_name: The name of the user (more meaningful than ID if the
            user has been deleted)
        status: The status of the operation
        attributes: A JSON document of attributes ("message" key is a common
            convention but others may be included for clarity)
        timestamp: The date/time the operation was performed
    """

    __tablename__ = "audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    root_id = Column(Integer, nullable=True)
    name = Column(String(128), nullable=True)
    operation = Column(Enum(OperationCode), index=True, nullable=False)
    object_type = Column(Enum(AuditType), index=False, nullable=True)
    object_id = Column(String(128), index=False, nullable=True)
    object_name = Column(String(256), nullable=True)
    user_id = Column(String(128), index=True, nullable=True)
    user_name = Column(String(256), index=False, nullable=True)
    status = Column(Enum(AuditStatus), index=True, nullable=False)
    reason = Column(Enum(AuditReason), nullable=True)
    attributes = Column(JSON, index=False, nullable=True)
    timestamp = Column(TZDateTime, nullable=False, default=TZDateTime.current_time)

    # Other global class properties

    BACKGROUND_USER = "BACKGROUND"  # Operation performed in background

    @staticmethod
    def create(
        root: Optional["Audit"] = None,
        user: Optional[User] = None,
        dataset: Optional[Dataset] = None,
        name: Optional[str] = None,
        operation: Optional[OperationCode] = None,
        object_type: Optional[AuditType] = None,
        object_id: Optional[str] = None,
        object_name: Optional[str] = None,
        user_id: Optional[str] = None,
        user_name: Optional[str] = None,
        status: Optional[AuditStatus] = None,
        reason: Optional[AuditReason] = None,
        attributes: Optional[JSONOBJECT] = None,
        **kwargs,
    ) -> "Audit":
        """
        A simple factory method to construct a new Audit setting and
        add it to the database.

        The "root" parameter is a shortcut to copy values from a reference
        "root" Audit record, for updates and finalization to a sequence.

        The "user" parameter pulls ID and name from a User record.

        The "dataset" parameter pulls object type, ID, and name from a Dataset
        record.

        Most columns are defined explicitly here primarily to allow completion
        in an IDE for convenience. The remaining less-used columns (primarily
        the raw root_id and timestamp, which should normally be defaulted) are
        accessible using kwargs.

        Args:
            root: The root (BEGIN) audit record of a long-running operation,
                from which the basic operation identification will be copied.
            user: The "user_id" and "user_name" columns are taken from the
                specified User object.
            dataset: Although "object_id" and "object_name" are not specific to
                the Dataset object, this is the most common. If dataset is
                specified, the "object_type", "object_id", and "object_name"
                will be set implicitly from the dataset object.
            name: A "name" for the operation (e.g., "index", "upload")
            operation: The CRUD operation code (OperationCode)
            object_type: The affected resource type (AuditType)
            object_id: An ID for the resource (if any)
            object_name: The name of the resource (if any)
            user_id: An ID for the user performing the operation
            user_name: The name of the user performing the operation
            status: The status of the operation (AuditStatus)
            reason: The status reason if applicable (AuditReason)
            attributes: JSON attributes (messages, modified properties)
            kwargs: Any other defined column names (e.g., root_id, timestamp)

        Returns:
            A new Audit object initialized with the parameters and added
            to the database.
        """

        audit = Audit(
            name=name,
            operation=operation,
            object_type=object_type,
            object_id=object_id,
            object_name=object_name,
            user_id=user_id,
            user_name=user_name,
            status=status,
            reason=reason,
            attributes=attributes,
            **kwargs,
        )
        if root:
            audit.root_id = root.id
            audit.name = root.name
            audit.operation = root.operation
            audit.object_type = root.object_type
            audit.object_id = root.object_id
            audit.object_name = root.object_name
            audit.user_id = root.user_id
            audit.user_name = root.user_name
        if user:
            audit.user_id = user.id
            audit.user_name = user.username
        if dataset:
            audit.object_type = AuditType.DATASET
            audit.object_id = dataset.resource_id
            audit.object_name = dataset.name
        audit.add()
        return audit

    @staticmethod
    def query(
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        dataset: Optional[Dataset] = None,
        user: Optional[str] = None,
        **kwargs,
    ) -> "list[Audit]":

        """
        Return a list of Audit objects matching the query parameters. The
        definition allows an exact search based on any column of the table
        using kwargs as well as date range queries using the 'start' and 'end'
        parameters.

        Args:
            start: The earliest timestamp of interest
            end: The most recent timestamp of interest
            dataset: Shortcut to match the type and object_id
            user: Alias for user_id
            operation, object_type, object_id, etc: exact match on column

        Raises:
            AuditSqlError: problem interacting with Database

        Returns:
            List of Audit objects matching the criteria
        """

        try:
            query = Database.db_session.query(Audit)
            if start and end:
                query = query.filter(Audit.timestamp.between(start, end))
            elif start:
                query = query.filter(Audit.timestamp >= start)
            elif end:
                query = query.filter(Audit.timestamp <= end)
            if user:
                query = query.filter(Audit.user_id == user)
            if dataset:
                query = query.filter(
                    Audit.object_type == AuditType.DATASET
                    and Audit.object_id == dataset.resource_id
                )
            if kwargs:
                query = query.filter_by(**kwargs)

            audit = query.order_by(Audit.timestamp).all()
        except SQLAlchemyError as e:
            raise AuditSqlError("finding", kwargs, str(e)) from e
        return audit

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
            return AuditDuplicate(self.id, cause)
        elif cause.find("NOT NULL constraint") != -1:
            return AuditNullKey(self.id, cause)
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
            raise AuditSqlError("adding", self.id, str(e)) from e

    def as_json(self) -> JSONOBJECT:
        return {
            "id": self.id,
            "root_id": self.root_id,
            "name": self.name,
            "operation": self.operation.name,
            "object_type": self.object_type.name if self.object_type else None,
            "object_id": self.object_id,
            "object_name": self.object_name,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "status": self.status.name if self.status else None,
            "reason": self.reason.name if self.reason else None,
            "attributes": self.attributes,
            "timestamp": self.timestamp.isoformat(),
        }
