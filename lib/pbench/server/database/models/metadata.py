import enum
import datetime
from pbench.server.database.database import Database
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import validates


class MetadataKeys(enum.Enum):
    FAVORITE = 1
    SAVED = 2


class Metadata(Database.Base):
    """ Metadata Model for storing user metadata details """

    # TODO: Think about the better name
    __tablename__ = "metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created = Column(DateTime, nullable=False, default=datetime.datetime.now())
    updated = Column(DateTime, nullable=False, default=datetime.datetime.now())
    value = Column(Text, unique=False, nullable=False)
    key = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)

    @validates("key")
    def evaluate_key(self, key, value):
        return MetadataKeys[value].value

    def get_json(self):
        return {
            "id": self.id,
            "value": self.value,
            "created": self.created,
            "updated": self.updated,
            "key": MetadataKeys(self.key).name,
        }

    @staticmethod
    def get_protected():
        return ["id", "created", "user_id"]

    @staticmethod
    def query(**kwargs):
        query = Database.db_session.query(Metadata)
        for attr, value in kwargs.items():
            print(getattr(Metadata, attr), value)
            query = query.filter(getattr(Metadata, attr) == value)
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
        Update the current user object with given keyword arguments
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
        Delete the metadata session with a given id
        :param username:
        :return:
        """
        try:
            metadata_query = Database.db_session.query(Metadata).filter_by(id=id)
            metadata_query.delete()
            Database.db_session.commit()
            return True
        except Exception:
            Database.db_session.rollback()
            raise
