import datetime
from threading import Thread
import time

import click

from pbench.server import PbenchServerConfig
from pbench.server.database import init_db


class Detail:
    """Encapsulate generation of additional diagnostics"""

    def __init__(self, detail: bool = False, errors: bool = False):
        """Initialize the object.

        Args:
            detail: True if detailed messages should be generated
            errors: True if individual file errors should be reported
        """
        self.detail = detail
        self.errors = errors

    def __bool__(self) -> bool:
        """Report whether detailed messages are enabled

        Returns:
            True if details are enabled
        """
        return self.detail

    def error(self, message: str):
        """Write a message if details are enabled.

        Args:
            message: Detail string
        """
        if self.errors:
            click.secho(f"|| {message}", fg="red")

    def message(self, message: str):
        """Write a message if details are enabled.

        Args:
            message: Detail string
        """
        if self.detail:
            click.echo(f"|| {message}")


class Verify:
    """Encapsulate -v status messages."""

    def __init__(self, verify: bool):
        """Initialize the object.

        Args:
            verify: True to write status messages.
        """
        self.verify = verify

    def __bool__(self) -> bool:
        """Report whether verification is enabled.

        Returns:
            True if verification is enabled.
        """
        return self.verify

    def status(self, message: str):
        """Write a message if verification is enabled.

        Args:
            message: status string
        """
        if self.verify:
            ts = datetime.datetime.now().astimezone()
            click.secho(f"({ts:%H:%M:%S}) {message}", fg="green")


class Watch:
    """Encapsulate a periodic status update.

    The active message can be updated at will; a background thread will
    periodically print the most recent status.
    """

    def __init__(self, interval: float):
        """Initialize the object.

        Args:
            interval: interval in seconds for status updates
        """
        self.start = time.time()
        self.interval = interval
        self.status = "starting"
        if interval:
            self.thread = Thread(target=self.watcher)
            self.thread.setDaemon(True)
            self.thread.start()

    def update(self, status: str):
        """Update status if appropriate.

        Update the message to be printed at the next interval, if progress
        reporting is enabled.

        Args:
            status: status string
        """
        self.status = status

    def watcher(self):
        """A worker thread to periodically write status messages."""

        while True:
            time.sleep(self.interval)
            now = time.time()
            delta = int(now - self.start)
            hours, remainder = divmod(delta, 3600)
            minutes, seconds = divmod(remainder, 60)
            click.secho(
                f"[{hours:02d}:{minutes:02d}:{seconds:02d}] {self.status}", fg="cyan"
            )


def config_setup(context: object) -> PbenchServerConfig:
    config = PbenchServerConfig.create(context.config)
    # We're going to need the DB to track dataset state, so setup DB access.
    init_db(config, None)
    return config
