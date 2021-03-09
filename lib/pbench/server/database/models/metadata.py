import datetime
from pbench.server.database.database import Database
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text


class Metadata(Database.Base):
    """ Metadata Model for storing user metadata details """

    # TODO: Think about the better name
    __tablename__ = "metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created = Column(DateTime, nullable=False, default=datetime.datetime.now())
    updated = Column(DateTime, nullable=False, default=datetime.datetime.now())
    config = Column(Text, unique=False, nullable=False)
    description = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))

    def __str__(self):
        return f"Url id: {self.id}, created on: {self.created}, description: {self.description}"

    def get_json(self):
        return {
            "id": self.id,
            "config": self.config,
            "description": self.description,
            "created": self.created,
            "updated": self.updated,
        }

    @staticmethod
    def get_protected():
        return ["id", "created"]

    @staticmethod
    def query(id=None, user_id=None):
        # Currently we would only query with single argument. Argument need to be either id/user_id
        if id:
            metadata = Database.db_session.query(Metadata).filter_by(id=id).first()
        elif user_id:
            # If the query parameter is user_id then we return the list of all the metadata linked to that user
            metadata = Database.db_session.query(Metadata).filter_by(user_id=user_id)
        else:
            metadata = None

        return metadata

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
