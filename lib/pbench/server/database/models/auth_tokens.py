import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from pbench.server.database.database import Database


class AuthToken(Database.Base):
    """Model for storing the active auth tokens associated with a user."""

    __tablename__ = "auth_tokens"
    id = Column(Integer, primary_key=True, autoincrement=True)
    auth_token = Column(String(500), unique=True, nullable=False, index=True)
    created = Column(DateTime, nullable=False)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        # no need to add index=True, all FKs have indexes
    )

    def __init__(self, auth_token: str):
        self.auth_token = auth_token
        self.created = datetime.datetime.now()

    @staticmethod
    def query(auth_token: str) -> Optional["AuthToken"]:
        """Find the given auth token in the database.

        Returns:
            An AuthToken object if found, otherwise None
        """
        # We currently only query token database with the given token.
        dbs = Database.db_session
        return dbs.query(AuthToken).filter_by(auth_token=auth_token).first()

    @staticmethod
    def delete(auth_token: str):
        """Delete the given auth token.

        Args:
            auth_token : the auth token to delete
        """
        dbs = Database.db_session
        try:
            dbs.query(AuthToken).filter_by(auth_token=auth_token).delete()
            dbs.commit()
        except Exception:
            dbs.rollback()
            raise

    @staticmethod
    def valid(auth_token: str) -> bool:
        """Validate an auth token using the database.

        Returns:
            True if valid (token is found in the database), False otherwise.
        """
        return bool(AuthToken.query(auth_token))
