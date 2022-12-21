from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

from pbench.server import NoOptionError, NoSectionError
from pbench.server.globals import server


class Database:
    # Create declarative base model that our model can inherit from
    Base = declarative_base()

    @staticmethod
    def get_engine_uri():
        try:
            engine_uri = server.config.get("database", "uri")
        except (NoSectionError, NoOptionError) as exc:
            engine_uri = None
            server.logger.error("Error in configuration file: {}", exc)
        return engine_uri

    @staticmethod
    def init_db():
        # WARNING:
        # Make sure all the models are imported before this function gets
        # called so that they will be registered properly on the metadata.
        # Otherwise metadata will not have any tables and create_all
        # functionality will do nothing.
        engine = create_engine(Database.get_engine_uri())
        Database.Base.metadata.create_all(bind=engine)
        server.db_session = scoped_session(
            sessionmaker(bind=engine, autocommit=False, autoflush=False)
        )
