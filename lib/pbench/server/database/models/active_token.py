from datetime import datetime
from typing import TypeVar

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from pbench.server.database.database import Database

AT = TypeVar("AT", bound="ActiveToken")


class ActiveToken(Database.Base):
    """Token model for storing the active auth tokens.

    Each token is associated with a given User object, and stores its
    expiration time.
    """

    __tablename__ = "active_token"
    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(500), unique=True, nullable=False, index=True)
    expiration = Column(DateTime, nullable=False, index=True)
    user_id = Column(
        Integer,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        # no need to add index=True, all FKs have indexes
    )
    user = relationship("User", back_populates="auth_tokens")

    def __init__(self, token: str, expiration: datetime):
        self.token = token
        self.expiration = expiration

    @staticmethod
    def query(token: str) -> AT:
        # We currently only query token database for a specific token.
        token_model = (
            Database.db_session.query(ActiveToken).filter_by(token=token).first()
        )
        return token_model

    @staticmethod
    def delete(token: str) -> None:
        """Deletes the given auth token if present.

        Args:
            token : auth token to delete
        """
        try:
            Database.db_session.query(ActiveToken).filter_by(token=token).delete()
            Database.db_session.commit()
        except Exception:
            Database.db_session.rollback()
            raise
