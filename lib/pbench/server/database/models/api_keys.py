from typing import Optional

from flask import current_app
import jwt
from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.orm import relationship

from pbench.server.database.database import Database
from pbench.server.database.models import commonDBException, TZDateTime
from pbench.server.database.models.users import User

# Module private constants
_TOKEN_ALG_INT = "HS256"


class APIKeyError(Exception):
    """A base class for errors reported by the APIKey class."""

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class APIKey(Database.Base):
    """Model for storing the API key associated with a user."""

    __tablename__ = "api_keys"
    api_key = Column(String(500), primary_key=True)
    created = Column(TZDateTime, nullable=False, default=TZDateTime.current_time)
    # ID of the owning user
    user_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Indirect reference to the owning User record
    user = relationship("User")

    def __str__(self):
        return f"key: {self.api_key}"

    class DuplicateValue(commonDBException):
        """Attempt to commit a duplicate unique value."""

        def __init__(self, api_key: "APIKey", cause: str):
            self.api_key = api_key
            self.cause = cause

        def __str__(self) -> str:
            return f"Duplicate api_key {self.api_key}: {self.cause}"

    class NullKey(commonDBException):
        """Attempt to commit an APIkey row with an empty required column."""

        def __init__(self, api_key: "APIKey", cause: str):
            self.api_key = api_key
            self.cause = cause

        def __str__(self) -> str:
            return f"Missing required key in {self.api_key.as_json()}: {self.cause}"

    def add(self):
        """Add an api_key object to the database."""
        try:
            Database.db_session.add(self)
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            self.logger.error("Can't add key:{} to DB: {}", str(self), str(e))
            raise commonDBException._decode(self, e) from e

    @staticmethod
    def query(key: str) -> Optional["APIKey"]:
        """Find the given api_key in the database.

        Returns:
            An APIKey object if found, otherwise None
        """
        # We currently only query api_key database with given api_key
        return Database.db_session.query(APIKey).filter_by(api_key=key).first()

    @staticmethod
    def delete(api_key: str):
        """Delete the given api_key.

        Args:
            api_key : the api_key to delete
        """
        dbs = Database.db_session
        try:
            dbs.query(APIKey).filter_by(api_key=api_key).delete()
            dbs.commit()
        except Exception as e:
            dbs.rollback()
            raise APIKeyError(f"Error deleting api_key from db : {e}") from e

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
