# -*- mode: python -*-

"""tool_meister_client API

The Tool Meister Client API encapsulates the steps required to send a message
to the Tool Data Sink with the action to be taken by the Tool Meisters,
processing the response that arrives from the Tool Data Sink for success or
failure.

A client is really only sending a message to the Tool Data Sink.  The Tool
Data Sink, in turn, coordinates all the behaviors related to the given action
for all the Tool Meisters, including forwarding the action payload to the Tool
Meisters.
"""

import logging
import os
from pathlib import Path
import sys
from typing import Any, Optional, Union

import state_signals

from pbench.agent.constants import cli_tm_allowed_actions, tm_allowed_actions
from pbench.agent.tool_group import ToolGroup
from pbench.agent.utils import RedisServerCommon

SIGNAL_RESPONSE_TIMEOUT = 100


class Client:
    """Context manager Tool Meister client.

    The constructor records the necessary client information for the context
    manager "enter" and "exit" methods to operate.
    """

    def __init__(
        self,
        redis_server=None,
        redis_host=None,
        redis_port=None,
        publisher_prefix=None,
        logger=None,
    ):
        """Construct a Tool Meister "client" object, given the host and port
        of a Redis server, or an existing Redis server object. The caller must
        specify a "prefix" to be used for the publisher name given to the
        State Signals sub-system.

        The caller can optionally provide a logger to be used.

        This constructor does not contact the Redis server, it just records
        the information for where that Redis server is.

        :redis_server:     - (optional) a previously construct Redis server
                             client object

        :redis_host:       - (optional) the IP or host name of the Redis
                             server to use

        :redis_port:       - (optional) the port on which the Redis server on
                             the given host name is listening

        :publisher_prefix: - (required) the prefix string to use for the
                             channel name

        :logger:           - (optional) a logger to use for reporting any
                             errors encountered (one will be created if not
                             provided)

        Typically, if you already have a Redis server client object, you would
        pass that in via "redis_server", otherwise you must pass a host name
        and port number for the Redis server to use.
        """
        assert (
            redis_server is None and (redis_host is not None and redis_port is not None)
        ) or (
            redis_server is not None and (redis_host is None and redis_port is None)
        ), "You must specify either a redis server object or a redis server host / port pair, but not both"

        self.redis_server = redis_server
        self.redis_host = redis_host
        self.redis_port = redis_port

        assert publisher_prefix is not None, "You must specify a publisher prefix"
        self.publisher_name = f"{publisher_prefix}-pbench-client"

        if logger is None:
            self.logger = logging.getLogger("tool-meister-client")
        else:
            self.logger = logger

    def __enter__(self) -> "Client":
        """On context entry, setup the connection with the Redis server using
        a SignalExporter instance."""
        if self.redis_server:
            self.logger.debug(
                "constructing SignalExporter() object using existing Redis"
                " connection, name: %s",
                self.publisher_name,
            )
            sig_pub = state_signals.SignalExporter(
                self.publisher_name, existing_redis_conn=self.redis_server
            )
        else:
            self.logger.debug(
                "constructing SignalExporter() object using host %s:%s," " name: %s",
                self.redis_host,
                self.redis_port,
                self.publisher_name,
            )
            sig_pub = state_signals.SignalExporter(
                self.publisher_name,
                redis_host=self.redis_host,
                redis_port=self.redis_port,
            )
        sig_pub.initialize_and_wait(
            1,
            list(tm_allowed_actions),
            tag="from_pbench_client",
        )
        self.sig_pub = sig_pub
        self.logger.debug("constructed SignalExporter() object")
        return self

    def __exit__(self, *args):
        """On context exit, just close down the to SignalExporter object."""
        self.sig_pub.shutdown()

    def publish(
        self,
        group: str,
        directory: Optional[Union[str, Path]],
        action: str,
        args: Optional[Any] = None,
    ) -> int:
        """Publish a state signal formed from the group, directory, action,
        and args arguments, using the SignalExporter instance.  It waits for
        responses from subscribers (TDS, and the TMs indirectly) before
        continuing.

        Returns 0 on success, 1 on failure; logs are also written for any
        errors encountered.

        """

        # The published message contains four pieces of information:
        #   {
        #     "action": "< 'init' | 'start' | 'stop' | 'send' | 'end' | 'terminate' >",
        #     "group": "< the tool group name for the tools to operate on >",
        #     "directory": "< the local directory path to store collected data >"
        #     "args": "< arbitrary argument payload for a particular action >"
        #   }
        # The caller of tool-meister-client must be sure the directory argument
        # is accessible by the Tool Data Sink instance.

        metadata = dict(
            group=group,
            # The "check" is necessary because sometimes directory is `None`
            # and we don't want to pass `str(None)`; the "conversion" is because
            # we're passing a "path-like object" which might be str or Path.
            directory=None if directory is None else str(directory),
            args=args,
        )
        self.logger.debug(
            "publish state signal for state %s with metadata: %s", action, metadata
        )
        try:
            resp, msgs = self.sig_pub.publish_signal(
                event=action,
                tag="from_pbench_client",
                metadata=metadata,
                timeout=SIGNAL_RESPONSE_TIMEOUT,
            )
        except Exception:
            self.logger.exception("Failed to publish client signal")
            return 1
        else:
            if resp != 0:
                self.logger.error("Missing or bad response from the TDS, %s", str(resp))
                ret_val = 1
                for responder, msg in msgs.items():
                    if msg != "success":
                        self.logger.warning(
                            "TDS responder %s reported: %s", responder, msg
                        )
            else:
                ret_val = 0
        return ret_val

    def terminate(self, group: str, interrupt=False) -> int:
        """terminate - send the terminate message for the tool group to the
        Tool Data Sink, which will forward to all the Tool Meisters to have
        them shut down.

        Returns 0 on success, non-zero on failure (errors logged on failure).
        """

        return self.publish(
            group=group,
            directory=None,
            action="terminate",
            args={"interrupt": interrupt},
        )


def main() -> int:
    """Main program for the Tool Meister client CLI.  The command line
    arguments are:

      group - the tool group on which the actions will be taken

      directory - the directory where data gathered from the actions will be
                  stored

      action - the particular action to take, can we one of "start", "stop",
               or "send" (see `cli_tm_allowed_actions`).
    """
    logger_name = os.path.basename(sys.argv[0])
    logger = logging.getLogger(logger_name)

    if os.environ.get("_PBENCH_TOOL_MEISTER_CLIENT_LOG_LEVEL") == "debug":
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logger.setLevel(log_level)
    sh = logging.StreamHandler()
    sh.setLevel(log_level)
    shf = logging.Formatter(f"{logger_name}: %(message)s")
    sh.setFormatter(shf)
    logger.addHandler(sh)

    try:
        group = sys.argv[1]
    except IndexError:
        logger.error("Missing group argument")
        return 1
    try:
        directory = sys.argv[2]
    except IndexError:
        logger.error("Missing directory argument")
        return 1
    try:
        action = sys.argv[3]
    except IndexError:
        logger.error("Missing action argument")
        return 1
    else:
        if action not in cli_tm_allowed_actions:
            logger.error(
                "Unrecognized action, '{}', allowed actions are: {}",
                action,
                cli_tm_allowed_actions,
            )
            return 1
        elif action == "kill":
            # FIXME: we need to implement the gritty method of killing all the
            # tool meisters, locally and remotely, and ensuring they are all
            # properly shut down.
            return 0

    try:
        # Load the tool group data
        tool_group = ToolGroup(group)
    except Exception:
        logger.exception("failed to load tool group data for '%s'", group)
        return 1
    else:
        if not tool_group.hostnames:
            # If a tool group has no tools registered, then there will be no
            # host names on which Tool Meisters would have been started, so we
            # can safely exit.
            return 0

    redis_server_env = os.environ.get("PBENCH_REDIS_SERVER", "")
    try:
        redis_server = RedisServerCommon(redis_server_env, "localhost")
    except RedisServerCommon.Err as exc:
        logger.error(str(exc))
        return exc.return_code

    with Client(
        redis_host=redis_server.host,
        redis_port=redis_server.port,
        publisher_prefix="cli",
        logger=logger,
    ) as client:
        ret_val = client.publish(group, directory, action)

    return ret_val
