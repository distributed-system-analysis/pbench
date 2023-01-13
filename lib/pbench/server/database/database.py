import socket
import time
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker
from sqlalchemy_utils import create_database, database_exists

from pbench.common.exceptions import BadConfig


class Database:
    # Create declarative base model that our model can inherit from
    Base = declarative_base()
    db_session = None

    @staticmethod
    def get_engine_uri(config):
        """Convenience method to hide knowledge of the database configuration."""
        return config.get("database", "uri")

    @staticmethod
    def wait_for_database(db_uri: str, timeout: int):
        """Wait for the database server to become available.

        While we encounter "connection refused", sleep one second, and then try
        again.  No connection attempt is made for a database URI without a host
        name.

        The timeout argument to `create_connection()` does not play into the
        retry logic, see:

          https://docs.python.org/3.9/library/socket.html#socket.create_connection

        Args:
            timeout : integer number of seconds to wait before giving up
                      attempts to connect to the database

        Raises:
            BadConfig : when the DB URI specifies a host without a port
            ConnectionRefusedError : after the timeout period has been exhausted
        """
        url = urlparse(db_uri)
        if not url.hostname:
            return
        if not url.port:
            raise BadConfig("Database URI must contain a port number")
        end = time.time() + timeout
        while True:
            try:
                with socket.create_connection((url.hostname, url.port), timeout=1):
                    break
            except ConnectionRefusedError:
                if time.time() > end:
                    raise
                time.sleep(1)

    @staticmethod
    def create_if_missing(db_uri, logger):
        """Create the database if it doesn't exist."""
        if not database_exists(db_uri):
            logger.info("Database {} doesn't exist", db_uri)
            create_database(db_uri)
            logger.info("Created database {}", db_uri)

    @staticmethod
    def init_db(server_config, logger):
        db_uri = Database.get_engine_uri(server_config)

        # Attach the logger and server config object to the base class for
        # database models to find.
        if logger and not hasattr(Database.Base, "logger"):
            Database.Base.logger = logger
        if server_config and not hasattr(Database.Base, "server_config"):
            Database.Base.config = server_config

        # WARNING:
        # Make sure all the models are imported before this function gets called
        # so that they will be registered properly on the metadata. Otherwise
        # metadata will not have any tables and create_all functionality will do
        # nothing.

        engine = create_engine(db_uri)
        Database.Base.metadata.create_all(bind=engine)
        Database.db_session = scoped_session(
            sessionmaker(bind=engine, autocommit=False, autoflush=False)
        )
        Database.Base.query = Database.db_session.query_property()
