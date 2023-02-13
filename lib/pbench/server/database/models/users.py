import copy
import enum
import re
from typing import Optional

from sqlalchemy import Column, Integer, JSON, String
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
        return f"Duplicate user setting in {self.user.as_json()}: {self.cause}"


class UserNullKey(UserError):
    """Attempt to commit an Audit row with an empty required column."""

    def __init__(self, user: "User", cause: str):
        self.user = user
        self.cause = cause

    def __str__(self) -> str:
        return f"Missing required key in {self.user.as_json()}: {self.cause}"


class UserProfileBadKey(UserError):
    """An unsupported profile key was specified.

    The error text will identify the profile key that was specified.
    """

    def __init__(self, key: str):
        self.key = key

    def __str__(self) -> str:
        return f"User profile key {self.key!r} is not supported"


class UserProfileBadStructure(UserError):
    """Invalid Profile structure encountered.

    A call to update found a level in the JSON document where
    the caller's key expected a nested JSON object but the type at that level
    is something else. For example, when `profile.user.email` finds that
    `profile.user` is a string, it's impossible to look up the `email` field.

    The error text will identify the key path and the expected key element that
    is missing.
    """

    def __init__(self, key: str):
        self.key = key

    def __str__(self) -> str:
        return f"Key value for {self.key!r} in profile is not a JSON object"


class User(Database.Base):
    """User Model for storing user related details."""

    __tablename__ = "users"

    # User profile keys
    #
    # SERVER is an internally maintained key namespace for additional metadata
    # relating to the server's management of user. The information here is
    # accessible to callers, but can't be changed.
    #
    # {"server.role": ["ADMIN"]}
    #
    # USER provides an open namespace allowing a user which is authenticated
    # to define arbitrary metadata accessible only to that authenticated user.
    # Each user can have its own unique value for this key, for example
    # "user.email"/"user.first_name".
    # Unauthenticated users can neither set nor read the user profile
    # in the USER namespace.
    # Note: USER namespace will be populated by the Server when the user access
    # the Pbench Server resources for the very first time.
    #
    # {"user.email": user@email.com}

    SERVER = "server"
    USER = "user"

    # Keys that are updatable by the user
    USER_UPDATEABLE_KEYS = [USER]

    # Keys that authenticated user can read
    PROFILE_KEYS = [USER, SERVER]

    _valid_key_charset = re.compile(r"[a-z0-9_.-]+")

    id = Column(Integer, primary_key=True, autoincrement=True)
    oidc_id = Column(String(255), unique=True, nullable=False)
    username = Column(String(255), unique=True, nullable=True)
    profile = Column(JSON, unique=False, nullable=True)
    dataset_metadata = relationship(
        "Metadata", back_populates="user", cascade="all, delete-orphan"
    )

    def __str__(self):
        return f"User, id: {self.id}, username: {self.username}"

    def get_json(self):
        return {
            "username": self.username,
            "profile": self.profile,
        }

    def verify_key(self, key):
        k = key.lower()
        # Check for exact match
        if k in self.USER_UPDATEABLE_KEYS:
            return True
        path = k.split(".")
        # Disallow ".." and trailing "."
        if "" in path:
            return False
        # Check for namespace match
        if path[0] not in self.USER_UPDATEABLE_KEYS:
            return False
        # Check that all open namespace keys are valid symbols
        return bool(re.fullmatch(self._valid_key_charset, k))

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
            raise UserSqlError("adding", self.as_json(), str(e)) from e

    def form_valid_dict(self, **kwargs) -> JSON:
        """Generates a valid dictionary from the given kwargs.

        This accept the kwargs in any of the following format example:
            1. {"user.department": "Perf_Scale", "user.company.name": "Red Hat"}
            2. {"user": {"company": {"location": "Westford"}}}
            3. {"user": {"company.location": "Westford"}}

        However, in any of the above format the first key had to be in the
        USER_UPDATEABLE_KEYS list otherwise it would raise UserProfileBadKey
        error.

        The dot separated keys will be transformed into a json
         e.g
            {"user.department": "Perf_Scale", "user.company.name": "Red Hat"}
        will be transformed into
            {user: {"department": "Perf_Scale", "company": {"name": "Red Hat"}}}
        """
        # Create a new empty dict object
        valid_dict = {}
        temp_update = valid_dict

        for key, value in kwargs.items():
            if not self.verify_key(key):
                raise UserProfileBadKey(key)
            keys = key.lower().split(".")
            for i in range(len(keys)):
                if i == len(keys) - 1:
                    temp_update[keys[i]] = value
                else:
                    val = temp_update.get(keys[i], {})
                    if not isinstance(val, dict):
                        raise UserProfileBadStructure(keys[i])
                    temp_update[keys[i]] = val
                    temp_update = temp_update[keys[i]]
            temp_update = valid_dict

        return valid_dict

    def update(self, new_profile: JSON):
        """Update the current profile of the user object with given keyword
        arguments.
        """
        try:
            # SQLAlchemy determines whether to perform an `update` based on the
            # Python object reference. We make a copy here to ensure that it
            # sees we've made a change.
            profile = copy.deepcopy(self.profile)

            for key in new_profile:
                profile[key].update(new_profile[key])
            setattr(self, "profile", profile)
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            raise UserSqlError("Updating", self.as_json(), str(e)) from e

    def delete(self):
        """Delete the user with a given username, except admin."""
        try:
            Database.db_session.delete(self)
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            raise UserSqlError("deleting", self.as_json(), str(e)) from e

    def is_admin(self) -> bool:
        """This method checks whether the given user has an admin role.

        This can be extended to groups as well for example a user belonging to
        certain group has only those privileges that are assigned to the
        group.

        Returns:
            True if the user's role is ADMIN, False otherwise.
        """
        return Roles.ADMIN.name in self.profile[self.SERVER]["roles"]

    def as_json(self) -> JSONOBJECT:
        """Return a JSON object for this User object.

        Returns:
            A JSONOBJECT with all the object fields mapped to appropriate names.
        """
        return {
            "id": self.id,
            "oidc_id": self.oidc_id,
            "username": self.username,
            "profile": self.profile,
        }
