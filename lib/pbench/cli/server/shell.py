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

PROG = "pbench-shell"


def app():
    try:
        server_config = get_server_config()
    except (ConfigFileNotSpecified, BadConfig) as e:
        print(e)
        sys.exit(1)
    return create_app(server_config)


def find_the_unicorn(logger: Logger):
    if site.ENABLE_USER_SITE:
        local = Path(site.getuserbase()) / "bin"
        if (local / "gunicorn").exists():
            # Use a `pip install --user` version of gunicorn
            os.environ["PATH"] = str(local) + ":" + os.environ["PATH"]
            logger.info(
                "Found a local unicorn: augmenting server PATH to {}",
                os.environ["PATH"],
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
    logger = get_pbench_logger(PROG, server_config)
    find_the_unicorn(logger)
    try:
        host = str(server_config.get("pbench-server", "bind_host"))
        port = str(server_config.get("pbench-server", "bind_port"))
        db = str(server_config.get("Postgres", "db_uri"))
        workers = str(server_config.get("pbench-server", "workers"))
        worker_timeout = str(server_config.get("pbench-server", "worker_timeout"))
        pbench_top_dir = server_config.get("pbench-server", "pbench-top-dir")
        pbench_install = server_config.get("pbench-server", "install-dir")
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
        logger.exception("Error fetching required configuration")
        sys.exit(1)

    cmd_line = [
        "gunicorn",
        "--workers",
        workers,
        "--timeout",
        worker_timeout,
        "--pid",
        "/run/pbench-server/gunicorn.pid",
        "--bind",
        f"{host}:{port}",
        "--log-syslog",
        "--log-syslog-prefix",
        "pbench-server",
    ]

    # When installed via RPM, the shebang in the gunicorn script includes a -s
    # which prevents Python from implicitly including the user site packages in
    # the sys.path configuration.  (Note that, when installed via Pip, the
    # shebang does not include this switch.)  This means that gunicorn itself,
    # but, more importantly, the user application which it runs, won't be able
    # to use any packages installed with the Pip --user switch, like our
    # requirements.txt contents. However, gunicorn provides the --pythonpath
    # switch which adds entries to the PYTHONPATH used to run the application.
    # So, we request that gunicorn add our current user site packages location
    # to the app's PYTHONPATH so that it can actually find the locally installed
    # packages as well as the pbench.pth file which points to the Pbench Server
    # package.
    if site.ENABLE_USER_SITE:
        adds = site.getusersitepackages() + "," + f"{pbench_install}/lib"
        cmd_line += ["--pythonpath", adds]

    cmd_line.append("pbench.cli.server.shell:app()")
    subprocess.run(cmd_line, cwd=f"{pbench_top_dir}/logs")
