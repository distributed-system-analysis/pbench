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
import sys

import state_signals

from pbench.agent.constants import cli_tm_allowed_actions, tm_allowed_actions
from pbench.agent.tool_group import ToolGroup
from pbench.agent.utils import RedisServerCommon


class Client:
    """Context manager Tool Meister client.

    The constructor records the necessary client information for the context
    manager "enter" and "exit" methods to operate.
    """

    def __init__(
        self,
        signal_publisher: state_signals.SignalExporter,
        to_be_shutdown: bool,
        logger: logging.Logger = None,
    ):
        """
        Construct a Tool Meister "client" object, given an initialized
        SignalExporter and whether it was created by the user or us.
        The caller can additionally optionally provide a logger to be used.

        :signal_publisher: - An initialized SignalExporter object for publishing
                             state signals
        :to_be_shutdown:   - A boolean flag to indicate whether or not we are
                             responsible for shutting down the SignalExporter
                             on exit (if we created it)
        :logger:           - (optional) a logger to use for reporting any errors
                             encountered (one will be created if not provided)
        """

        self.sig_pub = signal_publisher
        self._to_be_shutdown = to_be_shutdown

        if logger is None:
            self.logger = logging.getLogger("tool-meister-client")
        else:
            self.logger = logger

        if not self.sig_pub.subs:
            self.logger.warning(
                "TDS not subbed to TM-Client, missing guarantee of await"
            )

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *args):
        if self._to_be_shutdown:
            self.sig_pub.shutdown()

    @classmethod
    def create_with_exporter(
        cls,
        signal_publisher: state_signals.SignalExporter,
        logger: logging.Logger = None,
    ):
        return cls(signal_publisher, False, logger)

    @classmethod
    def create_with_redis(
        cls,
        redis_host: str,
        redis_port: str,
        publisher_name: str = "pbench_client",
        logger: logging.Logger = None,
    ):
        sig_pub = state_signals.SignalExporter(
            publisher_name, redis_host=redis_host, redis_port=redis_port
        )
        sig_pub.initialize_and_wait(
            1,
            list(tm_allowed_actions),
            tag="from_pbench_client",
        )
        return cls(sig_pub, True, logger)

    def _publish(self, group: str, directory: str, action: str, args=None) -> int:
        # The published message contains four pieces of information:
        #   {
        #     "action": "< 'init' | 'start' | 'stop' | 'send' | 'end' | 'terminate' >",
        #     "group": "< the tool group name for the tools to operate on >",
        #     "directory": "< the local directory path to store collected data >"
        #     "args": "< arbitrary argument payload for a particular action >"
        #   }
        # The caller of tool-meister-client must be sure the directory argument
        # is accessible by the Tool Data Sink instance.
        if directory:
            directory = str(directory)
        metadata = dict(group=group, directory=directory, args=args)
        self.logger.debug(
            f"publish state signal for state {action} with metadata: {metadata}"
        )
        try:
            resp, msgs = self.sig_pub.publish_signal(
                event=action, tag="from_pbench_client", metadata=metadata, timeout=100
            )
        except Exception:
            self.logger.exception("Failed to publish client signal")
            return 1
        else:
            if resp != 0:
                self.logger.error(f"Missing or bad response from the TDS, {resp}")
                ret_val = 1
                for responder, msg in msgs.items():
                    if msg != "success":
                        self.logger.warning(
                            f"TDS responder {responder} reported: {msg}"
                        )
            else:
                ret_val = 0
        return ret_val

    def publish(self, group: str, directory: str, action: str, args=None) -> int:
        """publish a state signal formed from the group, directory,
        action, and args arguments.

        Returns 0 on success, 1 on failure; logs are also written for any
        errors encountered.
        """
        if action not in tm_allowed_actions:
            self.logger.warning(f"Attempted to publish illegal action '{action}'")
            return 1

        return self._publish(
            group=group,
            directory=directory,
            action=action,
            args=args,
        )

    def terminate(self, group: str, interrupt=False) -> int:
        """terminate - send the terminate message for the tool group to the
        Tool Data Sink, which will forward to all the Tool Meisters to have
        them shut down.

        Returns 0 on success, non-zero on failure (errors logged on failure).
        """

        return self._publish(
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

    with Client.create_with_redis(
        redis_host=redis_server.host,
        redis_port=redis_server.port,
        logger=logger,
    ) as client:
        ret_val = client.publish(group, directory, action)

    return ret_val
