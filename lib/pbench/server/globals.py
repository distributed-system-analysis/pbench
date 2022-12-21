"""Pbench Server Context Variables

A simple module for providing a "server" namespace for context variables.
"""
from contextvars import ContextVar
import logging
from typing import Optional

from sqlalchemy.orm import scoped_session
from werkzeug.local import LocalProxy

from pbench.server import PbenchServerConfig


class _ServerCtx:
    """A simple context object for our server execution environment.

    The three attributes of server are:

        config : PbenchServerConfig
        logger : logging.Logger, as constructed by pbench.common.logger.get_pbench_logger()
        db_session : The current database session in play

    Typicaly use:

        from pbench.server.globals import server
        server.logger.info("hi")
    """

    def __init__(
        self, config: PbenchServerConfig = None, logger: logging.Logger = None
    ):
        self.config: PbenchServerConfig = config
        self.logger: logging.Logger = logger
        self.db_session: Optional[scoped_session] = None


_server_var = ContextVar("server", default=None)
server = LocalProxy(_server_var)


def init_server_ctx(config: PbenchServerConfig = None, logger: logging.Logger = None):
    """Set the server context variable to an instance of the _ServerCtx object."""
    cur_val = _server_var.get()
    assert cur_val is None, f"Server context already set: server = {cur_val!r}"
    _server_var.set(_ServerCtx(config, logger))


def destroy_server_ctx():
    """Destroy the current server context by setting it to `None`.

    Only used by the unit tests.
    """
    cur_val = _server_var.get()
    assert isinstance(
        cur_val, _ServerCtx
    ), f"Server context corrupted: server = {cur_val!r}"
    _server_var.set(None)
