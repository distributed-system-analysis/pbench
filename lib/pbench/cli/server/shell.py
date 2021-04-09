#!/bin/env python3

import subprocess
import sys

from configparser import NoSectionError, NoOptionError
from sqlalchemy_utils import database_exists, create_database

from pbench.common.exceptions import BadConfig, ConfigFileNotSpecified
from pbench.server.api import create_app, get_server_config
from pbench.server.database.database import Database
from pbench.common.logger import get_pbench_logger


def app():
    try:
        server_config = get_server_config()
    except (ConfigFileNotSpecified, BadConfig) as e:
        print(e)
        sys.exit(1)
    return create_app(server_config)


def main():
    try:
        server_config = get_server_config()
    except (ConfigFileNotSpecified, BadConfig) as e:
        print(e)
        sys.exit(1)
    logger = get_pbench_logger(__name__, server_config)
    try:
        host = str(server_config.get("pbench-server", "bind_host"))
        port = str(server_config.get("pbench-server", "bind_port"))
        db = str(server_config.get("Postgres", "db_uri"))
        workers = str(server_config.get("pbench-server", "workers"))

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
            "--pid",
            "/run/pbench-server/gunicorn.pid",
            "--bind",
            f"{host}:{port}",
            "pbench.cli.server.shell:app()",
        ]
    )
