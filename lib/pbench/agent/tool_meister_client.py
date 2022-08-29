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

import json
import logging
import os
import sys

import redis

from pbench.agent.constants import (
    api_tm_allowed_actions,
    cli_tm_allowed_actions,
    cli_tm_channel_prefix,
    tm_channel_suffix_from_client,
    tm_channel_suffix_to_client,
)
from pbench.agent.redis_utils import RedisChannelSubscriber
from pbench.agent.tool_group import ToolGroup
from pbench.agent.utils import RedisServerCommon


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
        channel_prefix=None,
        to_client_chan=None,
        logger=None,
    ):
        """Construct a Tool Meister "client" object, given the host and port
        of a Redis server.  The caller can optionally provide a logger to be
        used.

        This constructor does not contact the Redis server, it just records
        the information for where that Redis server is.

        :redis_server:   - (optional) a previously construct Redis server
                           client object
        :redis_host:     - (optional) the IP or host name of the Redis server
                           to use
        :redis_port:     - (optional) the port on which the Redis server on
                           the given host name is listening
        :channel_prefix: - (required) the prefix string to use for the channel
                           name
        :to_client_chan: - (optional) a previously constructed
                           RedisChannelSubscriber object (the caller ensures
                           it is for the same Redis server client object
                           given)
        :logger:         - (optional) a logger to use for reporting any errors
                           encountered (one will be created if not provided)

        Typically, if you already have a Redis server client object, you would
        pass that in via "redis_server", otherwise you must pass a host name
        and port number for the Redis server to use.

        If you already have a RedisChannelSubscriber object, you must provide
        the Redis server client object that was used to construct it.
        """
        assert (
            redis_server is None and (redis_host is not None and redis_port is not None)
        ) or (
            redis_server is not None and (redis_host is None and redis_port is None)
        ), "You must specify either a redis server object or a redis server host / port pair, but not both"

        self.redis_server = redis_server
        self.redis_host = redis_host
        self.redis_port = redis_port

        assert channel_prefix is not None, "You must specify a channel prefix"
        self.to_client_channel = f"{channel_prefix}-{tm_channel_suffix_to_client}"
        self.from_client_channel = f"{channel_prefix}-{tm_channel_suffix_from_client}"

        assert to_client_chan is None or redis_server is not None, (
            "You must specify a Redis server client object with a"
            " RedisChannelSubscriber object"
        )
        self.to_client_chan = to_client_chan

        if logger is None:
            self.logger = logging.getLogger("tool-meister-client")
        else:
            self.logger = logger

    def __enter__(self) -> "Client":
        """On context entry, setup the connection with the Redis server."""
        if self.redis_server is None:
            self.logger.debug("constructing Redis() object")
            try:
                self.redis_server = redis.Redis(
                    host=self.redis_host, port=self.redis_port, db=0
                )
            except Exception as e:
                self.logger.error(
                    "Unable to connect to redis server, %s:%s: %s",
                    self.redis_host,
                    self.redis_port,
                    e,
                )
                raise
            else:
                self.logger.debug("constructed Redis() object")

        if self.to_client_chan is None:
            self.to_client_chan = RedisChannelSubscriber(
                self.redis_server, self.to_client_channel
            )
        return self

    def __exit__(self, *args):
        """On context exit, just close down the to client channel object."""
        if self.to_client_chan is not None:
            self.to_client_chan.close()

    def publish(self, group, directory, action, args=None):
        """publish - marshal a JSON document formed from the group, directory,
        action, and args arguments.

        Returns 0 on success, 1 on failure; logs are also written for any
        errors encountered.
        """
        if action not in api_tm_allowed_actions:
            return 1
        # The published message contains four pieces of information:
        #   {
        #     "action": "< 'start' | 'stop' | 'send' | 'kill' >",
        #     "group": "< the tool group name for the tools to operate on >",
        #     "directory": "< the local directory path to store collected data >"
        #     "args": "< arbitrary argument payload for a particular action >"
        #   }
        # The caller of tool-meister-client must be sure the directory argument
        # is accessible by the Tool Data Sink instance.
        self.logger.debug("publish %s on chan %s", action, self.from_client_channel)
        msg = dict(action=action, group=group, directory=str(directory), args=args)
        try:
            num_present = self.redis_server.publish(
                self.from_client_channel, json.dumps(msg)
            )
        except Exception:
            self.logger.exception("Failed to publish client message")
            return 1
        else:
            self.logger.debug("published %s", self.from_client_channel)
            if num_present != 1:
                self.logger.error(
                    "Failed to publish to the TDS, encountered %d subscribers"
                    " on the channel",
                    num_present,
                )
                ret_val = 1
            else:
                ret_val = 0

        # Wait for an operational status message from the Tool Data Sink
        # reporting the combined response of the Tool Meisters.
        for data in self.to_client_chan.fetch_json(self.logger):
            try:
                kind = data["kind"]
                action_r = data["action"]
                status = data["status"]
            except Exception:
                self.logger.error("unrecognized status payload, %r", data)
                ret_val = 1
            else:
                if kind != "ds":
                    self.logger.warning("unrecognized kind in payload, %r", data)
                    ret_val = 1
                    continue
                if action_r != action:
                    self.logger.warning("unrecognized action in payload, %r", data)
                    ret_val = 1
                    continue
                if status != "success":
                    self.logger.warning(
                        "Status message not successful: '%s'",
                        status,
                    )
                    ret_val = 1
                break
        return ret_val

    def terminate(self, group, interrupt=False):
        """terminate - send the terminate message for the tool group to the
        Tool Data Sink, which will forward to all the Tool Meisters to have
        them shut down.

        Returns 0 on success, non-zero on failure (errors logged on failure).
        """
        ret_val = 0

        self.logger.debug("publish terminate on chan %s", self.from_client_channel)
        terminate_msg = dict(
            action="terminate",
            group=group,
            directory=None,
            args={"interrupt": interrupt},
        )
        try:
            num_present = self.redis_server.publish(
                self.from_client_channel, json.dumps(terminate_msg, sort_keys=True)
            )
        except Exception:
            self.logger.exception("Failed to publish terminate message")
            ret_val = 1
        else:
            if num_present != 1:
                self.logger.error(
                    "Failed to terminate TDS, encountered %d on the channel",
                    num_present,
                )
                ret_val = 1
        return ret_val


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
        channel_prefix=cli_tm_channel_prefix,
        logger=logger,
    ) as client:
        ret_val = client.publish(group, directory, action)

    return ret_val
