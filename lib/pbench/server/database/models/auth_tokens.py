from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from pbench.server.database.database import Database


class AuthToken(Database.Base):
    """Model for storing the active auth tokens associated with a user.

    Each token is associated with a given User object, and stores its
    expiration time.
    """

    __tablename__ = "auth_tokens"
    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(500), unique=True, nullable=False, index=True)
    expiration = Column(DateTime, nullable=False, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        # no need to add index=True, all FKs have indexes
    )
    user = relationship("User", back_populates="auth_tokens")

    @staticmethod
    def query(auth_token: str) -> Optional["AuthToken"]:
        """Find the given auth token in the database.

        Returns:
            An AuthToken object if found, otherwise None
        """
        # We currently only query token database for a specific token.
        dbs = Database.db_session
        return dbs.query(AuthToken).filter_by(token=auth_token).first()

    @staticmethod
    def delete(auth_token: str):
        """Delete the given auth token.

        If the auth token does not exist return silently.

        Args:
            auth_token : the auth token to delete
        """
        dbs = Database.db_session
        try:
            token = dbs.query(AuthToken).filter_by(token=auth_token)
            if not token:
                return
            token.delete()
            Database.db_session.commit()
        except Exception:
            dbs.rollback()
            raise
