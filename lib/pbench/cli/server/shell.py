from configparser import NoOptionError, NoSectionError
import os
from pathlib import Path
import site
import subprocess
import sys

from flask import Flask

from pbench.common import wait_for_uri
from pbench.common.exceptions import BadConfig
from pbench.common.logger import get_pbench_logger
from pbench.server.api import create_app, get_server_config
from pbench.server.auth import OpenIDClient
from pbench.server.database import init_db
from pbench.server.database.database import Database
from pbench.server.globals import init_server_ctx, server
from pbench.server.indexer import init_indexing

PROG = "pbench-shell"


def app() -> Flask:
    """External gunicorn application entry point."""
    return create_app(get_server_config())


def find_the_unicorn():
    """Add the location of the `pip install --user` version of gunicorn to the
    PATH if it exists.
    """
    local = Path(site.getuserbase()) / "bin"
    if (local / "gunicorn").exists():
        # Use a `pip install --user` version of gunicorn
        os.environ["PATH"] = ":".join([str(local), os.environ["PATH"]])
        server.logger.info(
            "Found a local unicorn: augmenting server PATH to {}",
            os.environ["PATH"],
        )


def generate_crontab_if_necessary(crontab_dir: str, bin_dir: Path, cwd: str) -> int:
    """Generate and install the crontab for the Pbench Server.

    If a crontab file already exists, no action is taken, otherwise a crontab
    file is created using `pbench-create-crontab` and then installed using the
    `crontab` command.

    If either of those operations fail, the crontab file is removed.

    Args:
        crontab_dir : directory where crontab files are stored
        bin_dir : directory where pbench commands are stored
        cwd : the current working directory to use when generating files

    Returns:
        0 on success, 1 on failure.
    """
    ret_val = 0
    crontab_f = Path(crontab_dir) / "crontab"
    if not crontab_f.exists():
        os.environ["PATH"] = ":".join([str(bin_dir), os.environ["PATH"]])
        # Create the crontab file from the server configuration.
        cp = subprocess.run(["pbench-create-crontab", crontab_dir], cwd=cwd)
        if cp.returncode != 0:
            server.logger.error(
                "Failed to create crontab file from configuration: {}", cp.returncode
            )
            ret_val = 1
        else:
            # Install the created crontab file.
            cp = subprocess.run(["crontab", f"{crontab_dir}/crontab"], cwd=cwd)
            if cp.returncode != 0:
                server.logger.error("Failed to install crontab file: {}", cp.returncode)
                ret_val = 1
    if ret_val != 0:
        crontab_f.unlink(missing_ok=True)
    return ret_val


def run_gunicorn() -> int:
    """Setup of the Gunicorn Pbench Server Flask application.

    Returns:
        1 on error, or the gunicorn sub-process status code
    """
    if site.ENABLE_USER_SITE:
        find_the_unicorn()
    try:
        host = server.config.get("pbench-server", "bind_host")
        port = str(server.config.get("pbench-server", "bind_port"))
        db_uri = server.config.get("database", "uri")
        db_wait_timeout = int(server.config.get("database", "wait_timeout"))
        es_uri = server.config.get("Indexing", "uri")
        es_wait_timeout = int(server.config.get("Indexing", "wait_timeout"))
        workers = str(server.config.get("pbench-server", "workers"))
        worker_timeout = str(server.config.get("pbench-server", "worker_timeout"))
        crontab_dir = server.config.get("pbench-server", "crontab-dir")
        server.config.get("flask-app", "secret-key")
    except (NoOptionError, NoSectionError) as exc:
        server.logger.error("Error fetching required configuration: {}", exc)
        return 1

    server.logger.info(
        "Waiting at most {:d} seconds for database instance {} to become available.",
        db_wait_timeout,
        db_uri,
    )
    try:
        wait_for_uri(db_uri, db_wait_timeout)
    except BadConfig as exc:
        server.logger.error(f"{exc}")
        return 1
    except ConnectionRefusedError:
        server.logger.error("Database {} not responding", db_uri)
        return 1

    server.logger.info(
        "Waiting at most {:d} seconds for the Elasticsearch instance {} to become available.",
        es_wait_timeout,
        es_uri,
    )
    try:
        wait_for_uri(es_uri, es_wait_timeout)
    except BadConfig as exc:
        server.logger.error(f"{exc}")
        return 1
    except ConnectionRefusedError:
        server.logger.error("Elasticsearch {} not responding", es_uri)
        return 1

    try:
        oidc_server = OpenIDClient.wait_for_oidc_server()
    except OpenIDClient.NotConfigured as exc:
        server.logger.warning("OpenID Connect client not configured, {}", exc)
    else:
        server.logger.info("Pbench server using OIDC server {}", oidc_server)

    # Multiple gunicorn workers will attempt to connect to the DB; rather than
    # attempt to synchronize them, detect a missing DB (from the database URI)
    # and create it here. It's safer to do this here, where we're
    # single-threaded.
    server.logger.info("Performing database setup")
    Database.create_if_missing(db_uri)
    try:
        init_db()
    except (NoOptionError, NoSectionError) as exc:
        server.logger.error("Invalid database configuration: {}", exc)
        return 1

    # Multiple cron jobs will attempt to file reports with the Elasticsearch
    # instance when they start and finish, causing them to all to try to
    # initialize the templates in the Indexing sub-system.  To avoid race
    # conditions that can create stack traces, we initialize the indexing sub-
    # system before we start the cron jobs.
    server.logger.info("Performing Elasticsearch indexing setup")
    try:
        init_indexing(PROG)
    except (NoOptionError, NoSectionError) as exc:
        server.logger.error("Invalid indexing configuration: {}", exc)
        return 1

    server.logger.info("Generating new crontab file, if necessary")
    ret_val = generate_crontab_if_necessary(
        crontab_dir, server.config.BINDIR, server.config.log_dir
    )
    if ret_val != 0:
        return ret_val

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
        adds = f"{site.getusersitepackages()},{server.config.LIBDIR}"
        cmd_line += ["--pythonpath", adds]

    cmd_line.append("pbench.cli.server.shell:app()")
    server.logger.info("Starting Gunicorn Pbench Server application")
    cp = subprocess.run(cmd_line, cwd=server.config.log_dir)
    server.logger.info(
        "Gunicorn Pbench Server application exited with {}", cp.returncode
    )
    return cp.returncode


def main() -> int:
    """Wrapper performing general error handling here allowing for the heavy
    lifting to be performed in run_gunicorn().

    Returns:
        0 on success, 1 on error
    """
    try:
        config = get_server_config()
        logger = get_pbench_logger(PROG, config)
        init_server_ctx(config, logger)
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1

    try:
        return run_gunicorn()
    except Exception:
        logger.exception("Unhandled exception running gunicorn")
        return 1
