from typing import Optional

from flask import current_app
import jwt
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from pbench.server import JSONOBJECT
from pbench.server.database.database import Database
from pbench.server.database.models import decode_integrity_error, TZDateTime
from pbench.server.database.models.users import User

# Module private constants
_TOKEN_ALG_INT = "HS256"


class APIKeyError(Exception):
    """A base class for errors reported by the APIKey class."""

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class DuplicateApiKey(APIKeyError):
    """Attempt to commit a duplicate unique value."""

    def __init__(self, cause: str):
        self.cause = cause

    def __str__(self) -> str:
        return f"Duplicate api_key: {self.cause}"


class NullKey(APIKeyError):
    """Attempt to commit an APIkey row with an empty required column."""

    def __init__(self, cause: str):
        self.cause = cause

    def __str__(self) -> str:
        return f"Missing required value: {self.cause}"


class APIKey(Database.Base):
    """Model for storing the API key associated with a user."""

    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, autoincrement=True)
    api_key = Column(String(500), unique=True, nullable=False)
    created = Column(TZDateTime, nullable=False, default=TZDateTime.current_time)
    name = Column(String(128), nullable=True)
    # ID of the owning user
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Indirect reference to the owning User record
    user = relationship("User")

    def __str__(self):
        return f"API key {self.api_key}"

    def add(self):
        """Add an api_key object to the database."""
        try:
            Database.db_session.add(self)
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            self.logger.error("Can't add {} to DB: {}", str(self), str(e))
            decode_exc = decode_integrity_error(
                e, on_duplicate=DuplicateApiKey, on_null=NullKey
            )
            if decode_exc is e:
                raise APIKeyError(str(e)) from e
            else:
                raise decode_exc from e

    @staticmethod
    def query(**kwargs) -> Optional["APIKey"]:
        """Find the given api_key in the database.

        Returns:
            An APIKey object if found, otherwise None
        """

        return Database.db_session.query(APIKey).filter_by(**kwargs).first()

    def query_by_user(user: str) -> Optional["APIKey"]:
        """Find the given api_key in the database.

        Returns:
            List of APIKey object if found, otherwise []
        """

        return (
            Database.db_session.query(APIKey)
            .filter_by(user=user)
            .order_by(APIKey.id)
            .all()
        )

    def delete(self):
        """Remove the api_key instance from the database."""
        try:
            Database.db_session.delete(self)
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            raise APIKeyError(f"Error deleting api_key from db : {e}") from e

    def as_json(self) -> JSONOBJECT:
        """Return a JSON object for this APIkey object.

        Returns:
            A JSONOBJECT with all the object fields mapped to appropriate names.
        """
        return {
            "id": self.id,
            "name": self.name,
            "key": self.api_key,
            "created_at": self.created.isoformat() if self.created else None,
        }

    @staticmethod
    def generate_api_key(user: User):
        """Creates an `api_key` for the requested user

        Returns:
            `api_key` or raises `APIKeyError`
        """
        user_obj = user.get_json()
        current_utc = TZDateTime.current_time()
        payload = {
            "iat": current_utc,
            "user_id": user_obj["id"],
            "username": user_obj["username"],
        }
        try:
            generated_api_key = jwt.encode(
                payload, current_app.secret_key, algorithm=_TOKEN_ALG_INT
            )
        except (
            jwt.InvalidIssuer,
            jwt.InvalidIssuedAtError,
            jwt.InvalidAlgorithmError,
            jwt.PyJWTError,
        ):
            current_app.logger.exception(
                "Could not encode the JWT api_key for user: {} and the payload is : {}",
                user,
                payload,
            )
            raise APIKeyError("Could not encode the JWT api_key for the user")
        return generated_api_key
