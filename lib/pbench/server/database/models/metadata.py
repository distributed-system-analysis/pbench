import datetime
from dateutil import parser
from pbench.server.database.database import Database
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey


class MetadataModel(Database.Base):
    """ Metadata Model for storing user metadata details """

    # TODO: Think about the better name
    __tablename__ = "metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created = Column(DateTime, nullable=False)
    updated = Column(DateTime, nullable=False)
    config = Column(String(255), unique=False, nullable=False)
    description = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'))

    def __init__(self, created, config, description, user_id):
        self.created = parser.parse(created)
        self.updated = datetime.datetime.now()
        self.config = config
        self.description = description
        self.user_id = user_id

    def __str__(self):
        return f"Url id: {self.id}, created on: {self.created}, description: {self.description}"

    def as_dict(self):
        return {c.name: str(getattr(self, c.name)) for c in self.__table__.columns}