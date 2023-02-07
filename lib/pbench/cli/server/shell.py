from configparser import NoOptionError, NoSectionError
from logging import Logger
import os
from pathlib import Path
import site
import subprocess
import sys

from flask import Flask

from pbench.common.logger import get_pbench_logger
from pbench.server import PbenchServerConfig
from pbench.server.api import create_app, get_server_config
from pbench.server.auth import OpenIDClient
from pbench.server.database import init_db
from pbench.server.database.database import Database

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


def generate_crontab_if_necessary(
    crontab_dir: str, bin_dir: Path, cwd: str, logger: Logger
) -> int:
    """Generate and install the crontab for the Pbench Server.

    If a crontab file already exists, no action is taken, otherwise a crontab
    file is created using `pbench-create-crontab` and then installed using the
    `crontab` command.

    If either of those operations fail, the crontab file is removed.

    Return 0 on success, 1 on failure.
    """
    ret_val = 0
    crontab_f = Path(crontab_dir) / "crontab"
    if not crontab_f.exists():
        os.environ["PATH"] = ":".join([str(bin_dir), os.environ["PATH"]])
        # Create the crontab file from the server configuration.
        cp = subprocess.run(["pbench-create-crontab", crontab_dir], cwd=cwd)
        if cp.returncode != 0:
            logger.error(
                "Failed to create crontab file from configuration: {}", cp.returncode
            )
            ret_val = 1
        else:
            # Install the created crontab file.
            cp = subprocess.run(["crontab", f"{crontab_dir}/crontab"], cwd=cwd)
            if cp.returncode != 0:
                logger.error("Failed to install crontab file: {}", cp.returncode)
                ret_val = 1
    if ret_val != 0:
        crontab_f.unlink(missing_ok=True)
    return ret_val


def run_gunicorn(server_config: PbenchServerConfig, logger: Logger) -> int:
    """Setup of the Gunicorn Pbench Server Flask application.

    Returns:
        1 on error, or the gunicorn sub-process status code
    """
    if site.ENABLE_USER_SITE:
        find_the_unicorn(logger)
    try:
        host = server_config.get("pbench-server", "bind_host")
        port = str(server_config.get("pbench-server", "bind_port"))
        db_uri = server_config.get("database", "uri")
        db_wait_timeout = int(server_config.get("database", "wait_timeout"))
        workers = str(server_config.get("pbench-server", "workers"))
        worker_timeout = str(server_config.get("pbench-server", "worker_timeout"))
        crontab_dir = server_config.get("pbench-server", "crontab-dir")
        server_config.get("flask-app", "secret-key")
    except (NoOptionError, NoSectionError) as exc:
        logger.error("Error fetching required configuration: {}", exc)
        return 1

    logger.info("Pbench server using database {}", db_uri)

    logger.debug("Waiting for database instance to become available.")
    try:
        Database.wait_for_database(db_uri, db_wait_timeout)
    except ConnectionRefusedError:
        logger.error("Database {} not responding", db_uri)
        return 1

    try:
        oidc_server = OpenIDClient.wait_for_oidc_server(server_config, logger)
    except OpenIDClient.NotConfigured as exc:
        logger.warning("OpenID Connect client not configured, {}", exc)
    else:
        logger.info("Pbench server using OIDC server {}", oidc_server)

    # Multiple gunicorn workers will attempt to connect to the DB; rather than
    # attempt to synchronize them, detect a missing DB (from the database URI)
    # and create it here. It's safer to do this here, where we're
    # single-threaded.
    Database.create_if_missing(db_uri, logger)
    try:
        init_db(server_config, logger)
    except (NoOptionError, NoSectionError) as exc:
        logger.error("Invalid database configuration: {}", exc)
        return 1

    ret_val = generate_crontab_if_necessary(
        crontab_dir, server_config.BINDIR, server_config.log_dir, logger
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
        adds = f"{site.getusersitepackages()},{server_config.LIBDIR}"
        cmd_line += ["--pythonpath", adds]

    cmd_line.append("pbench.cli.server.shell:app()")
    cp = subprocess.run(cmd_line, cwd=server_config.log_dir)
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
