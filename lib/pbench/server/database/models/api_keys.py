from typing import Optional

from flask import current_app
import jwt
from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.orm import relationship

from pbench.server.database.database import Database
from pbench.server.database.models import TZDateTime
from pbench.server.database.models.users import User


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

    def add(self):
        """Add an api_key object to the database."""
        try:
            Database.db_session.add(self)
            Database.db_session.commit()
        except Exception as e:
            Database.db_session.rollback()
            self.logger.error("Can't add api_key to DB: {}", str(e))
            raise APIKeyError(f"Error adding api_key to db : {e}") from e

    @staticmethod
    def query(key: str) -> Optional["APIKey"]:
        """Find the given api_key in the database.

        Returns:
            An APIKey object if found, otherwise None
        """
        # We currently only query api_key database with given api_key
        api_key = Database.db_session.query(APIKey).filter_by(api_key=key).first()
        return api_key

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
        except Exception:
            dbs.rollback()
            raise

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
                payload, current_app.secret_key, algorithm="HS256"
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
