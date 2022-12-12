from http import HTTPStatus
from logging import Logger
import os
from pathlib import Path
import site
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from sqlalchemy_utils import create_database, database_exists

from pbench.common.exceptions import BadConfig, ConfigFileNotSpecified
from pbench.common.logger import get_pbench_logger
from pbench.server.api import create_app, get_server_config
from pbench.server.database import init_db

PROG = "pbench-shell"


def app():
    """External gunicorn application entry point."""
    try:
        server_config = get_server_config()
    except (ConfigFileNotSpecified, BadConfig) as e:
        print(e)
        sys.exit(1)
    return create_app(server_config)


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


def wait_for_database(db_uri: str, timeout: int):
    """Wait for the database server to become available.  While we encounter
    "connection refused", sleep one second, and then try again.

    No connection attempt is made for a database URI without a hostname.

    The timeout argument to `create_connection()` does not play into the retry
    logic, see:

      https://docs.python.org/3.9/library/socket.html#socket.create_connection

    Arguments:

        timeout: integer number of seconds to wait before giving up attempts to
                 connect to the database

    Raises a BadConfig exception if the DB URI specifies a host without a port,
    and the ConnectionRefusedError enountered after the timeout.
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


def keycloak_connection(oidc_server: str, logger: Logger) -> int:
    """
     Checks if the Keycloak server is up and accepting the connections.
     The connection check does the GET request on the oidc server /health
     endpoint and the sample response returned by the /health endpoint looks
     like the following:
        {
            "status": "UP", # if the server is up
            "checks": []
        }
     Note: The Keycloak server needs to be started with health-enabled on.
     Args:
        oidc_server: OIDC server to verify
        logger: logger
    Returns:
        0 if successful
        1 if unsuccessful
    """
    session = requests.Session()
    # The connection check will retry multiple times unless successful, viz.,
    # [0.0s, 4.0s, 8.0s, 16.0s, ..., 120.0s]. urllib3 will sleep for:
    # {backoff factor} * (2 ^ ({number of total retries} - 1)) seconds between
    # the retries. However, the sleep will never be longer than backoff_max
    # which defaults to 120.0s More detailed documentation on Retry and
    # backoff_factor can be found at:
    # https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html#module-urllib3.util.retry
    retry = Retry(
        total=8,
        backoff_factor=2,
        status_forcelist=tuple(int(x) for x in HTTPStatus if x != 200),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)

    # We will also need to retry the connection if the health status is not UP.
    ret_val = 1
    for _ in range(5):
        try:
            response = session.get(f"{oidc_server}/health")
            response.raise_for_status()
        except Exception:
            logger.exception("Error connecting to the OIDC client")
            break
        if response.json().get("status") == "UP":
            logger.debug("OIDC server connection verified")
            ret_val = 0
            break
        else:
            logger.error(
                "OIDC client not running, OIDC server response: {}", response.json()
            )
            retry.sleep()
    return ret_val


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


def main():
    """Setup of the Gunicorn Pbench Server Flask application.

    If an error is encountered during setup, system exit is invoked with an
    exit code of 1.  Otherwise, the exit code of the gunicorn subprocess is
    used.
    """
    try:
        server_config = get_server_config()
    except (ConfigFileNotSpecified, BadConfig) as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    logger = get_pbench_logger(PROG, server_config)
    if site.ENABLE_USER_SITE:
        find_the_unicorn(logger)
    try:
        host = server_config._get_conf("pbench-server", "bind_host")
        port = str(server_config._get_conf("pbench-server", "bind_port"))
        db_uri = server_config._get_conf("database", "uri")
        db_wait_timeout = int(server_config._get_conf("database", "wait_timeout"))
        workers = str(server_config._get_conf("pbench-server", "workers"))
        worker_timeout = str(server_config._get_conf("pbench-server", "worker_timeout"))
        crontab_dir = server_config._get_conf("pbench-server", "crontab-dir")
    except BadConfig as exc:
        logger.error("Error fetching required configuration: {}", exc)
        sys.exit(1)

    logger.info("Pbench server using database {}", db_uri)

    logger.debug("Waiting for database instance to become available.")
    try:
        wait_for_database(db_uri, db_wait_timeout)
    except ConnectionRefusedError:
        logger.error("Database {} not responding", db_uri)
        sys.exit(1)

    try:
        oidc_server = server_config._get_conf("authentication", "server_url")
    except BadConfig as exc:
        logger.warning("KeyCloak not configured, {}", exc)
    else:
        logger.debug("Waiting for OIDC server to become available.")
        ret_val = keycloak_connection(oidc_server, logger)
        if ret_val != 0:
            sys.exit(ret_val)
        logger.info("Pbench server using OIDC server {}", oidc_server)

    # Multiple gunicorn workers will attempt to connect to the DB; rather than
    # attempt to synchronize them, detect a missing DB (from the database URI)
    # and create it here. It's safer to do this here, where we're
    # single-threaded.
    if not database_exists(db_uri):
        logger.info("Database {} doesn't exist", db_uri)
        create_database(db_uri)
        logger.info("Created database {}", db_uri)
    init_db(server_config, logger)

    ret_val = generate_crontab_if_necessary(
        crontab_dir, server_config.BINDIR, server_config.log_dir, logger
    )
    if ret_val != 0:
        sys.exit(ret_val)

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
    sys.exit(cp.returncode)
