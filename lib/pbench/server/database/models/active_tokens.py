import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

from pbench.server.database.database import Database


class ActiveTokens(Database.Base):
    """Token model for storing the active auth tokens at any given time"""

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

    def __init__(self, token):
        self.token = token
        self.created = datetime.datetime.now()

    @staticmethod
    def query(token):
        # We currently only query token database with given token
        token_model = (
            Database.db_session.query(ActiveTokens).filter_by(token=token).first()
        )
        return token_model

    @staticmethod
    def delete(auth_token):
        """
        Deletes the given auth token
        :param auth_token:
        :return:
        """
        try:
            Database.db_session.query(ActiveTokens).filter_by(token=auth_token).delete()
            Database.db_session.commit()
        except Exception:
            Database.db_session.rollback()
            raise

    @staticmethod
    def valid(auth_token):
        # check whether auth token is in the active database
        return bool(ActiveTokens.query(auth_token))
