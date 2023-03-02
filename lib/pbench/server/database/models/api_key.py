from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from pbench.server.database.database import Database


class APIKey(Database.Base):
    """Model for storing the API key associated with a user."""

    __tablename__ = "api_key"
    id = Column(Integer, primary_key=True, autoincrement=True)
    api_key = Column(String(500), unique=True, nullable=False, index=True)
    created = Column(DateTime, nullable=False)
    expiration = Column(DateTime, nullable=False)
    user_id = Column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    def __init__(self, api_key: str, created, expiration):
        self.api_key = api_key
        self.created = created
        self.expiration = expiration

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
            api_key_delete = dbs.query(APIKey).filter_by(api_key=api_key)
            if not api_key_delete:
                return
            api_key_delete.delete()
            Database.db_session.commit()
        except Exception:
            dbs.rollback()
            raise

    @staticmethod
    def valid(api_key: str) -> bool:
        """Validate an api_key using the database.

        Returns:
            True if valid (api_key is found in the database), False otherwise.
        """
        return bool(APIKey.query(api_key))
