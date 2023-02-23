import enum
from typing import Optional

from sqlalchemy import Column, Integer, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import relationship

from pbench.server import JSONOBJECT
from pbench.server.database.database import Database


class Roles(enum.Enum):
    ADMIN = 1


class UserError(Exception):
    """A base class for errors reported by the user class.

    It is never raised directly, but may be used in "except" clauses.
    """


class UserSqlError(UserError):
    """SQLAlchemy errors reported through User operations.

    The exception will identify the operation being performed and the config
    key; the cause will specify the original SQLAlchemy exception.
    """

    def __init__(self, operation: str, params: JSONOBJECT, cause: str):
        self.operation = operation
        self.params = params
        self.cause = cause

    def __str__(self) -> str:
        return f"Error {self.operation} {self.params!r}: {self.cause}"


class UserDuplicate(UserError):
    """Attempt to commit a duplicate unique value."""

    def __init__(self, user: "User", cause: str):
        self.user = user
        self.cause = cause

    def __str__(self) -> str:
        return f"Duplicate user setting in {self.user.get_json()}: {self.cause}"


class UserNullKey(UserError):
    """Attempt to commit an Audit row with an empty required column."""

    def __init__(self, user: "User", cause: str):
        self.user = user
        self.cause = cause

    def __str__(self) -> str:
        return f"Missing required key in {self.user.get_json()}: {self.cause}"


class User(Database.Base):
    """User Model for storing user related details."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    oidc_id = Column(String(255), unique=True, nullable=False)
    username = Column(String(255), unique=True, nullable=True)
    dataset_metadata = relationship(
        "Metadata", back_populates="user", cascade="all, delete-orphan"
    )
    _roles = Column(String(255), unique=False, nullable=True)

    @property
    def roles(self):
        if self._roles:
            return [x for x in self._roles.split(";")]
        else:
            return []

    @roles.setter
    def roles(self, value):
        if isinstance(value, list):
            self._roles = ";".join(value)
        elif isinstance(value, str):
            self._roles = value
        else:
            raise UserSqlError("Adding role", value, "Value is not a str or list")

    def __str__(self):
        return f"User, id: {self.id}, username: {self.username}"

    def get_json(self):
        return {"username": self.username, "id": self.id}

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
            return UserDuplicate(self, cause)
        elif "NOT NULL constraint" in cause:
            return UserNullKey(self, cause)
        return exception

    @staticmethod
    def query(id=None, oidc_id=None, username=None, email=None) -> Optional["User"]:
        """Find a user using one of the provided arguments.

        The first argument which is not None is used in the query.  The order
        in which the arguments are considered follows the method signature.

        Returns:
            A User object if a user is found, None otherwise.
        """
        if id:
            user = Database.db_session.query(User).filter_by(id=id).first()
        elif oidc_id:
            user = Database.db_session.query(User).filter_by(oidc_id=oidc_id).first()
        elif username:
            user = Database.db_session.query(User).filter_by(username=username).first()
        else:
            user = None
        return user

    @staticmethod
    def query_all() -> list["User"]:
        return Database.db_session.query(User).all()

    def add(self):
        """Add the current user object to the database."""
        try:
            Database.db_session.add(self)
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            if isinstance(e, IntegrityError):
                raise self._decode(e) from e
            raise UserSqlError("adding", self.get_json(), str(e)) from e

    def update(self, **kwargs):
        """Update the current profile of the user object with given keyword
        arguments.
        """
        try:
            for key, value in kwargs.items():
                setattr(self, key, value)
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            if isinstance(e, IntegrityError):
                raise self._decode(e) from e
            raise UserSqlError("Updating", self.get_json(), str(e)) from e

    def delete(self):
        """Delete the user with a given username, except admin."""
        try:
            Database.db_session.delete(self)
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            raise UserSqlError("deleting", self.get_json(), str(e)) from e

    def is_admin(self) -> bool:
        """This method checks whether the given user has an admin role.

        This can be extended to groups as well for example a user belonging to
        certain group has only those privileges that are assigned to the
        group.

        Returns:
            True if the user's role is ADMIN, False otherwise.
        """
        return Roles.ADMIN.name in self.roles

    def as_json(self) -> JSONOBJECT:
        """Return a JSON object for this User object.

        Returns:
            A JSONOBJECT with all the object fields mapped to appropriate names.
        """
        return {
            "id": self.id,
            "oidc_id": self.oidc_id,
            "username": self.username,
            "roles": self.roles,
        }
