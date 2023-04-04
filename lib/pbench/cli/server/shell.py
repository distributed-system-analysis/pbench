from configparser import NoOptionError, NoSectionError
from logging import Logger
import os
from pathlib import Path
import site
import subprocess
import sys

from flask import Flask
import sdnotify

from pbench.common import wait_for_uri
from pbench.common.exceptions import BadConfig
from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.api import create_app, get_server_config
from pbench.server.auth import OpenIDClient
from pbench.server.database import init_db
from pbench.server.database.database import Database
from pbench.server.indexer import init_indexing

PROG = "pbench-shell"


def app() -> Flask:
    """External gunicorn application entry point."""
    return create_app(get_server_config())


def find_the_unicorn(logger: Logger):
    """Add the location of the `pip install --user` version of gunicorn to the
    PATH if it exists.
    """
    local = Path(site.getuserbase()) / "bin"
    if (local / "gunicorn").exists():
        # Use a `pip install --user` version of gunicorn
        os.environ["PATH"] = ":".join([str(local), os.environ["PATH"]])
        logger.info(
            "Found a local unicorn: augmenting server PATH to {}",
            os.environ["PATH"],
        )


def run_gunicorn(server_config: PbenchServerConfig, logger: Logger) -> int:
    """Setup of the Gunicorn Pbench Server Flask application.

    Returns:
        1 on error, or the gunicorn sub-process status code
    """
    notifier = sdnotify.SystemdNotifier()

    notifier.notify("STATUS=Identifying configuration")
    if site.ENABLE_USER_SITE:
        find_the_unicorn(logger)
    try:
        host = server_config.get("pbench-server", "bind_host")
        port = str(server_config.get("pbench-server", "bind_port"))
        db_uri = server_config.get("database", "uri")
        db_wait_timeout = int(server_config.get("database", "wait_timeout"))
        es_uri = server_config.get("Indexing", "uri")
        es_wait_timeout = int(server_config.get("Indexing", "wait_timeout"))
        workers = str(server_config.get("pbench-server", "workers"))
        worker_timeout = str(server_config.get("pbench-server", "worker_timeout"))
        server_config.get("flask-app", "secret-key")
    except (NoOptionError, NoSectionError) as exc:
        logger.error("Error fetching required configuration: {}", exc)
        notifier.notify("STOPPING=1")
        notifier.notify("STATUS=Unable to configure gunicorn")
        return 1

    notifier.notify("STATUS=Waiting for database")
    logger.info(
        "Waiting at most {:d} seconds for database instance {} to become available.",
        db_wait_timeout,
        db_uri,
    )
    try:
        wait_for_uri(db_uri, db_wait_timeout)
    except BadConfig as exc:
        logger.error(f"{exc}")
        notifier.notify("STOPPING=1")
        notifier.notify(f"STATUS=Bad DB config {exc}")
        return 1
    except ConnectionRefusedError:
        logger.error("Database {} not responding", db_uri)
        notifier.notify("STOPPING=1")
        notifier.notify("STATUS=DB not responding")
        return 1

    notifier.notify("STATUS=Waiting for Elasticsearch instance")
    logger.info(
        "Waiting at most {:d} seconds for the Elasticsearch instance {} to become available.",
        es_wait_timeout,
        es_uri,
    )
    try:
        wait_for_uri(es_uri, es_wait_timeout)
    except BadConfig as exc:
        logger.error(f"{exc}")
        notifier.notify("STOPPING=1")
        notifier.notify(f"STATUS=Bad index config {exc}")
        return 1
    except ConnectionRefusedError:
        logger.error("Index {} not responding", es_uri)
        notifier.notify("STOPPING=1")
        notifier.notify("STATUS=Index service not responding")
        return 1

    notifier.notify("STATUS=Initializing OIDC")
    try:
        oidc_server = OpenIDClient.wait_for_oidc_server(server_config, logger)
    except OpenIDClient.NotConfigured as exc:
        logger.warning("OpenID Connect client not configured, {}", exc)
        notifier.notify("STOPPING=1")
        notifier.notify("STATUS=OPENID broker not responding")
    else:
        logger.info("Pbench server using OIDC server {}", oidc_server)

    # Multiple gunicorn workers will attempt to connect to the DB; rather than
    # attempt to synchronize them, detect a missing DB (from the database URI)
    # and create it here. It's safer to do this here, where we're
    # single-threaded.
    notifier.notify("STATUS=Initializing database")
    logger.info("Performing database setup")
    Database.create_if_missing(db_uri, logger)
    try:
        init_db(server_config, logger)
    except (NoOptionError, NoSectionError) as exc:
        logger.error("Invalid database configuration: {}", exc)
        notifier.notify("STOPPING=1")
        notifier.notify(f"STATUS=Error initializing database: {exc}")
        return 1

    # Multiple cron jobs will attempt to file reports with the Elasticsearch
    # instance when they start and finish, causing them to all to try to
    # initialize the templates in the Indexing sub-system.  To avoid race
    # conditions that can create stack traces, we initialize the indexing sub-
    # system before we start the cron jobs.
    notifier.notify("STATUS=Initializing Elasticsearch")
    logger.info("Performing Elasticsearch indexing setup")
    try:
        init_indexing(PROG, server_config, logger)
    except (NoOptionError, NoSectionError) as exc:
        logger.error("Invalid indexing configuration: {}", exc)
        notifier.notify("STOPPING=1")
        notifier.notify(f"STATUS=Invalid indexing config {exc}")
        return 1

    notifier.notify("READY=1")

    # Beginning of the gunicorn command to start the pbench-server.
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
        adds = f"{site.getusersitepackages()},{server_config.LIBDIR}"
        cmd_line += ["--pythonpath", adds]

    cmd_line.append("pbench.cli.server.shell:app()")
    logger.info("Starting Gunicorn Pbench Server application")
    notifier.notify("STATUS=Starting gunicorn")
    cp = subprocess.run(cmd_line, cwd=server_config.log_dir)
    logger.info("Gunicorn Pbench Server application exited with {}", cp.returncode)
    notifier.notify(f"STATUS=Gunicorn terminated with {cp.returncode}")
    notifier.notify("STOPPING=1")
    return cp.returncode


def main() -> int:
    """Wrapper performing general error handling here allowing for the heavy
    lifting to be performed in run_gunicorn().

    Returns:
        0 on success, 1 on error
    """
    try:
        server_config = get_server_config()
        logger = get_pbench_logger(PROG, server_config)
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1

    try:
        return run_gunicorn(server_config, logger)
    except Exception:
        logger.exception("Unhandled exception running gunicorn")
        return 1
