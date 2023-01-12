import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

from pbench.server import NoOptionError, NoSectionError


class Database:
    # Create declarative base model that our model can inherit from
    Base = declarative_base()
    db_session = None

    @staticmethod
    def get_engine_uri(config, logger):
        engine_uri = None
        try:
            engine_uri = config.get("database", "uri")
        except (NoSectionError, NoOptionError) as exc:
            msg = "Error in configuration file: {}"
            if logger:
                logger.error(msg, exc)
            else:
                print(msg.format(exc), file=sys.stderr)
        return engine_uri

    @staticmethod
    def init_db(server_config, logger):
        # Attach the logger and server config object to the base class for
        # database models to find
        if logger and not hasattr(Database.Base, "logger"):
            Database.Base.logger = logger
        if server_config and not hasattr(Database.Base, "server_config"):
            Database.Base.config = server_config

        # WARNING:
        # Make sure all the models are imported before this function gets called
        # so that they will be registered properly on the metadata. Otherwise
        # metadata will not have any tables and create_all functionality will do nothing

        engine = create_engine(Database.get_engine_uri(server_config, logger))
        Database.Base.metadata.create_all(bind=engine)
        Database.db_session = scoped_session(
            sessionmaker(bind=engine, autocommit=False, autoflush=False)
        )
        Database.Base.query = Database.db_session.query_property()
