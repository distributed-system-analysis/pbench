import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from pbench.server.database.database import Database


class ActiveTokens(Database.Base):
    """Model for storing the active auth tokens associated with a user."""

    __tablename__ = "active_tokens"
    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(500), unique=True, nullable=False, index=True)
    created = Column(DateTime, nullable=False)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        # no need to add index=True, all FKs have indexes
    )

    def __init__(self, auth_token: str):
        self.token = auth_token
        self.created = datetime.datetime.now()

    @staticmethod
    def query(auth_token: str) -> Optional["ActiveTokens"]:
        """Find the given auth token in the database.

        Returns:
            An ActiveTokens object if found, otherwise None
        """
        # We currently only query token database with given token
        active_token = (
            Database.db_session.query(ActiveTokens).filter_by(token=auth_token).first()
        )
        return active_token

    @staticmethod
    def delete(auth_token: str):
        """Delete the given auth token.

        Args:
            auth_token : the auth token to delete
        """
        try:
            Database.db_session.query(ActiveTokens).filter_by(token=auth_token).delete()
            Database.db_session.commit()
        except Exception:
            Database.db_session.rollback()
            raise

    @staticmethod
    def valid(auth_token: str) -> bool:
        """Validate an auth token using the database.

        Returns:
            True if valid (token is found in the database), False otherwise.
        """
        return bool(ActiveTokens.query(auth_token))
