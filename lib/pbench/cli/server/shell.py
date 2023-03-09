from configparser import NoOptionError, NoSectionError
from logging import Logger
import os
from pathlib import Path
import site
import subprocess
import sys
from threading import Event, Thread
from typing import Optional

from flask import Flask

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


class PbenchIndexer:
    """Managed the context of the indexer subprocesses."""

    def __init__(self, bin_dir: Path, cwd: Path, logger: Logger):
        """Construct the subprocess tracker state.

        Args:
            bin_dir: Where to find the `pbench-index` command
            cwd: Where to set the command working directory
            logger: Python logger for feedback.
        """
        self.bin_dir = bin_dir
        self.cwd = cwd
        self.logger = logger
        self.indexer: Optional[subprocess.Popen] = None
        self.reindexer: Optional[subprocess.Popen] = None
        self.shutoff: Event = Event()
        self.reaper: Optional[Thread] = None

    def start_indexer(self):
        """Isolate starting the primary indexer as a subprocess.

        NOTE: we specify the 'python3' command explicitly rather than relying
        on the shebang to avoid the intermediate `env python` command which
        complicates reaping.
        """
        self.indexer = subprocess.Popen(
            ["python3", self.bin_dir / "pbench-index"], cwd=self.cwd
        )
        self.logger.info("Index process running in pid {}", self.indexer.pid)

    def start_reindexer(self):
        """Isolate starting the secondary reindexer as a subprocess.

        TODO: I'm not sure we really want to retain the old "reindex". For one
        thing, re-indexing with existing index documents may be problematic,
        especially if the new indexer doesn't overwrite every document. A
        better mechanism would be to delete all the existing documents using
        the index-map and then we can simply READY the INDEX operation.

        NOTE: we specify the 'python3' command explicitly rather than relying
        on the shebang to avoid the intermediate `env python` command which
        complicates reaping.
        """
        self.reindexer = subprocess.Popen(
            ["python3", self.bin_dir / "pbench-index", "--re-index"], cwd=self.cwd
        )
        self.logger.info("Re-index process running in pid {}", self.reindexer.pid)

    def watch_indexers(self):
        """A thread to monitor our two indexer subprocesses.

        It'll periodically check `wait` for terminated processes in the process
        group. If the pid matches the indexer or reindexer, restart them. If a
        gunicorn work fails (or any other subprocess that might occur) just log
        it.
        """
        self.logger.info("Reaper thread is starting")
        while not self.shutoff.wait(20.0):
            self.logger.info("Reaper ...")

            pid, status = os.waitpid(0, os.WNOHANG)
            if pid == self.indexer.pid:
                self.logger.warning("Indexer {} died with {}", pid, status)
                self.start_indexer()
            elif pid == self.reindexer.pid:
                self.logger.warning("Re-indexer {} died with {}", pid, status)
                self.start_reindexer()
            elif pid != 0:
                self.logger.error(
                    "Unexpected subprocess {} termination with {}", pid, status
                )

    def start(self):
        """Start an indexer subprocess.

        The indexer will run in the background, periodically checking for datasets
        with the INDEX operation enabled. It will loop until it finds no more, and
        then sleep for a while before trying again.

        TODO: This starts an indexer and a re-indexer, even though "re-index"
        isn't cleanly supported. (I suspect we should blow away all current
        index documents, if any, and then simply "INDEX", if we really want to
        support this. For now, this is creating both processes.)

        Args:
            bin_dir: Where to find the pbench-index command
            cwd: Where to set the working directory
            logger: A Python logger

        Returns:
            The Popen of the created process so it can be tracked and stopped.
        """
        self.logger.info("Starting indexer subprocesses")
        self.reaper = Thread(target=self.watch_indexers, daemon=True)
        self.reaper.start()
        self.start_indexer()
        self.start_reindexer()

    def shutdown(self):
        """Stop the indexer

        We shut down the indexers with SIGTERM, which will terminate the index
        loop when finished with the current dataset. Other termination signals
        are ignored during most of the loop.
        """

        # Stop the background indexer after the server shuts down
        self.logger.info(
            "Shutting down background indexers {}, {}",
            self.indexer.pid,
            self.reindexer.pid,
        )

        # Shut down the watcher first so it doesn't re-spawn our indexers
        self.shutoff.set()
        self.reaper.join(20.0)

        # Ask both indexers to terminate, and wait for them
        self.indexer.terminate()
        self.reindexer.terminate()
        self.logger.info("Waiting for indexer termination...")
        istat = self.indexer.wait(5.0)
        ristat = self.reindexer.wait(5.0)
        self.logger.info("Waits terminated with {}, {}", istat, ristat)
        return istat if istat else ristat


def run_server(server_config: PbenchServerConfig, logger: Logger) -> int:
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
        es_uri = server_config.get("Indexing", "uri")
        es_wait_timeout = int(server_config.get("Indexing", "wait_timeout"))
        workers = str(server_config.get("pbench-server", "workers"))
        worker_timeout = str(server_config.get("pbench-server", "worker_timeout"))
        server_config.get("flask-app", "secret-key")
    except (NoOptionError, NoSectionError) as exc:
        logger.error("Error fetching required configuration: {}", exc)
        return 1

    logger.info(
        "Waiting at most {:d} seconds for database instance {} to become available.",
        db_wait_timeout,
        db_uri,
    )
    try:
        wait_for_uri(db_uri, db_wait_timeout)
    except BadConfig as exc:
        logger.error(f"{exc}")
        return 1
    except ConnectionRefusedError:
        logger.error("Database {} not responding", db_uri)
        return 1

    logger.info(
        "Waiting at most {:d} seconds for the Elasticsearch instance {} to become available.",
        es_wait_timeout,
        es_uri,
    )
    try:
        wait_for_uri(es_uri, es_wait_timeout)
    except BadConfig as exc:
        logger.error(f"{exc}")
        return 1
    except ConnectionRefusedError:
        logger.error("Elasticsearch {} not responding", es_uri)
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
    logger.info("Performing database setup")
    Database.create_if_missing(db_uri, logger)
    try:
        init_db(server_config, logger)
    except (NoOptionError, NoSectionError) as exc:
        logger.error("Invalid database configuration: {}", exc)
        return 1

    # Multiple cron jobs will attempt to file reports with the Elasticsearch
    # instance when they start and finish, causing them to all to try to
    # initialize the templates in the Indexing sub-system.  To avoid race
    # conditions that can create stack traces, we initialize the indexing sub-
    # system before we start the cron jobs.
    logger.info("Performing Elasticsearch indexing setup")
    try:
        init_indexing(PROG, server_config, logger)
    except (NoOptionError, NoSectionError) as exc:
        logger.error("Invalid indexing configuration: {}", exc)
        return 1

    # Start the Pbench indexers as subprocesses
    indexer = PbenchIndexer(server_config.BINDIR, server_config.TMP, logger)
    try:
        indexer.start()
    except Exception:
        logger.exception("Indexer startup failed")
        return 1

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
    cp = subprocess.run(cmd_line, cwd=server_config.log_dir)

    # NOTE: `systemctl stop` cleanly terminates the processes in the process
    # group with SIGTERM, and we never get here, but for the record:
    logger.info("Gunicorn Pbench Server application exited with {}", cp.returncode)
    istat = indexer.shutdown()
    return istat if istat else cp.returncode


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
        return run_server(server_config, logger)
    except Exception:
        logger.exception("Unhandled exception running gunicorn")
        return 1
