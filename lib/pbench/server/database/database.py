from logging import DEBUG
from pathlib import Path
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, Query, scoped_session, sessionmaker
from sqlalchemy_utils import create_database, database_exists

from pbench.server.globals import server


class Database:
    # Create declarative base model that our model can inherit from
    Base = declarative_base()

    @staticmethod
    def get_engine_uri() -> str:
        """Convenience method to hide knowledge of the database configuration.

        Returns:
            string URI
        """
        return server.config.get("database", "uri")

    @staticmethod
    def create_if_missing(db_uri: str):
        """Create the database if it doesn't exist.

        Args:
            db_uri: The server's DB URI
        """
        if not database_exists(db_uri):
            server.logger.info("Database {} doesn't exist", db_uri)
            create_database(db_uri)
            server.logger.info("Created database {}", db_uri)

    @staticmethod
    def init_db():
        """Initialize the server's database."""
        db_uri = Database.get_engine_uri(server.config)

        # WARNING:
        # Make sure all the models are imported before this function gets called
        # so that they will be registered properly on the metadata. Otherwise
        # metadata will not have any tables and create_all functionality will do
        # nothing.

        engine = create_engine(db_uri)
        db_url = urlparse(db_uri)
        if db_url.scheme == "sqlite":
            Database.Base.metadata.create_all(bind=engine)
        else:
            alembic_cfg = Config()
            alembic_cfg.set_main_option(
                "script_location", str(Path(__file__).parent / "alembic")
            )
            alembic_cfg.set_main_option("prepend_sys_path", ".")
            with engine.begin() as connection:
                alembic_cfg.attributes["connection"] = connection
                command.upgrade(alembic_cfg, "head")
        Database.db_session = scoped_session(
            sessionmaker(bind=engine, autocommit=False, autoflush=False)
        )
        Database.Base.query = Database.db_session.query_property()

        # Although most of the Pbench Server currently works with the default
        # SQLAlchemy transaction management, some parts rely on true atomic
        # transactions and need a better isolation level.
        # NOTE: In PostgreSQL we might use a slightly looser integrity level
        # like "REPEATABLE READ", however as this isn't supported in sqlite3
        # we're using the strictest "SERIALIZABLE" level.
        Database.maker = sessionmaker(
            bind=engine.execution_options(isolation_level="SERIALIZABLE")
        )

    @staticmethod
    def dump_query(query: Query):
        """Dump a fully resolved SQL query if DEBUG logging is enabled

        Args:
            query:  A SQLAlchemy Query object
        """
        if server.logger.isEnabledFor(DEBUG):
            q_str = query.statement.compile(compile_kwargs={"literal_binds": True})
            server.logger.debug("QUERY {}", q_str)
