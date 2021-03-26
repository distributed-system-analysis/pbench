import datetime
from pbench.server.database.database import Database
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text


class UserMetadata(Database.Base):
    """ Metadata Model for storing user metadata details """

    # TODO: Think about the better name
    __tablename__ = "user_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created = Column(DateTime, nullable=False, default=datetime.datetime.now())
    updated = Column(DateTime, nullable=False, default=datetime.datetime.now())
    value = Column(Text, unique=False, nullable=False)
    key = Column(String(128), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)

    def get_json(self, include):
        data = {}
        for key in include:
            data.update({key: getattr(self, key)})
        return data

    @staticmethod
    def get_protected():
        return ["id", "created", "user_id"]

    @staticmethod
    def query(**kwargs):
        query = Database.db_session.query(UserMetadata)
        for attr, value in kwargs.items():
            query = query.filter(getattr(UserMetadata, attr) == value)
        return query.all()

    def add(self):
        """
        Add the current metadata object to the database
        """
        try:
            Database.db_session.add(self)
            Database.db_session.commit()
        except Exception:
            Database.db_session.rollback()
            raise

    def update(self, **kwargs):
        """
        Update the current metadata object with given keyword arguments
        """
        try:
            for key, value in kwargs.items():
                setattr(self, key, value)
            Database.db_session.commit()
        except Exception:
            Database.db_session.rollback()
            raise

    @staticmethod
    def delete(id):
        """
        Delete the metadata object with a given id
        :param id: metadata_object_id
        :return:
        """
        try:
            metadata_query = Database.db_session.query(UserMetadata).filter_by(id=id)
            metadata_query.delete()
            Database.db_session.commit()
            return True
        except Exception:
            Database.db_session.rollback()
            raise
