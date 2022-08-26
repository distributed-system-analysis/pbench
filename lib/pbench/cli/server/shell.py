from configparser import NoOptionError, NoSectionError
from logging import Logger
import os
from pathlib import Path
import site
import subprocess
import sys

from sqlalchemy_utils import create_database, database_exists

from pbench.common.exceptions import BadConfig, ConfigFileNotSpecified
from pbench.common.logger import get_pbench_logger
from pbench.server.api import create_app, get_server_config
from pbench.server.database.database import Database


def app():
    try:
        server_config = get_server_config()
    except (ConfigFileNotSpecified, BadConfig) as e:
        print(e)
        sys.exit(1)
    return create_app(server_config)


def find_the_unicorn(logger: Logger) -> str:
    local = Path(site.getuserbase()) / "bin"
    if (local / "gunicorn").exists():
        # Use a `pip install --user` version of gunicorn
        os.environ["PATH"] = str(local) + ":" + os.environ["PATH"]
        logger.info(
            "Found a local unicorn: augmenting server PATH to {}", os.environ["PATH"]
        )


def main():
    os.environ[
        "_PBENCH_SERVER_CONFIG"
    ] = "/opt/pbench-server/lib/config/pbench-server.cfg"
    try:
        server_config = get_server_config()
    except (ConfigFileNotSpecified, BadConfig) as e:
        print(e)
        sys.exit(1)
    logger = get_pbench_logger(__name__, server_config)
    find_the_unicorn(logger)
    try:
        host = str(server_config.get("pbench-server", "bind_host"))
        port = str(server_config.get("pbench-server", "bind_port"))
        db = str(server_config.get("Postgres", "db_uri"))
        workers = str(server_config.get("pbench-server", "workers"))
        worker_timeout = str(server_config.get("pbench-server", "worker_timeout"))
        logger.info("Pbench server using database {}", db)

        # Multiple gunicorn workers will attempt to connect to the DB; rather
        # than attempt to synchronize them, detect a missing DB (from the
        # postgres URI) and create it here. It's safer to do this here,
        # where we're single-threaded.
        if not database_exists(db):
            logger.info("Postgres DB {} doesn't exist", db)
            create_database(db)
            logger.info("Created DB {}", db)
        Database.init_db(server_config, logger)
    except (NoOptionError, NoSectionError):
        logger.exception(f"{__name__}: ERROR")
        sys.exit(1)

    subprocess.run(
        [
            "gunicorn",
            "--workers",
            workers,
            "--timeout",
            worker_timeout,
            "--pid",
            "/run/pbench-server/gunicorn.pid",
            "--bind",
            f"{host}:{port}",
            "--access-logfile",
            "/var/log/pbench-server/access_log",
            "--error-logfile",
            "/var/log/pbench-server/error_log",
            "pbench.cli.server.shell:app()",
        ]
    )
