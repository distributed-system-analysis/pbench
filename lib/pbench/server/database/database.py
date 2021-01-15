from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from pbench.server import NoOptionError, NoSectionError


class Database:
    # Create declarative base model that our model can inherit from
    Base = declarative_base()

    @staticmethod
    def get_engine_uri(config, logger):
        try:
            psql = config.get("Postgres", "db_uri")
            return psql
        except (NoSectionError, NoOptionError):
            logger.error(
                "Failed to find an [Postgres] section" " in configuration file."
            )
            return None

    @staticmethod
    def init_db(server_config, logger):
        # Attach the logger to the base class for models to find
        if not hasattr(Database.Base, "logger"):
            Database.Base.logger = logger

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
