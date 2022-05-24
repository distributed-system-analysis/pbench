#!/usr/bin/env python3
# -*- mode: python -*-

"""pbench-tool-meister-stop

Responsible for ending persistent tools, collecting any requested system
information, recording any necessary metadata about the Tool Meisters, and
stopping all local/remote tool meisters, closing down the local data sink, and
finally the local redis server.
"""

import logging
import os
import sys
import time

from argparse import ArgumentParser, Namespace
from pathlib import Path

from pbench.agent.constants import cli_tm_channel_prefix
from pbench.agent.tool_group import BadToolGroup, ToolGroup
from pbench.agent.tool_meister_client import Client
from pbench.agent.utils import (
    RedisServerCommon,
    cli_verify_sysinfo,
    error_log,
    info_log,
)


def is_running(pid: int) -> bool:
    """is_running - Is the given PID running?

    See https://stackoverflow.com/questions/7653178/wait-until-a-certain-process-knowing-the-pid-end

    Return True if a PID is running, else False if not.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def wait_for_pid(pid: int) -> None:
    """wait_for_pid - wait for a process to actually stop running."""
    while is_running(pid):
        time.sleep(0.1)


class RedisServer(RedisServerCommon):
    """RedisServer - an encapsulation of the handling of the Redis server
    specification for pbench-tool-meister-stop.

    The constructor is enhanced to find the optional local Redis server pid
    file, and the additional method, locally_managed(), keys off of its
    presence.
    """

    def __init__(self, spec: str, benchmark_run_dir: Path, def_host_name: str):
        super().__init__(spec, def_host_name)
        try:
            self.pid_file = (benchmark_run_dir / "tm" / "redis.pid").resolve(
                strict=True
            )
        except FileNotFoundError:
            pass
        else:
            # Since this Redis server is locally managed, communication to it
            # will always be through the "localhost" interface.
            self.host = "localhost"

    def locally_managed(self) -> bool:
        return self.pid_file is not None


def graceful_shutdown(
    benchmark_run_dir: Path,
    redis_server: RedisServer,
    logger: logging.Logger,
) -> int:
    """Attempt to cleanly shut down the previously created Tool Data Sink, and
    the Redis server.

    The assumption/assertion here is that the tool meister "stop" command is run
    on the same node as the tool meister "start" command ran, creating the local
    Tool Data Sink and the optional local Tool Meister. We want to make sure
    anything "local" to this stop command is shut down gracefully before we
    report back to the user.  If Tool Meisters from remote nodes have already
    reported that they have received the "terminate" message, then we trust they
    will shutdown gracefully themselves.

    Returns 0 on success, 1 on failure (logging any unexpected exceptions)
    """
    try:
        tds_pid_file = benchmark_run_dir / "tm" / "pbench-tool-data-sink.pid"
        try:
            pid_str = tds_pid_file.read_text()
        except FileNotFoundError:
            pass
        else:
            tds_pid = int(pid_str)
            logger.debug("waiting for tool-data-sink (%d) to exit", tds_pid)
            wait_for_pid(tds_pid)
    except Exception:
        logger.exception("Exception encountered waiting for tool-data-sink")
        ret_val = 1
    else:
        ret_val = 0

    try:
        ltm_pid_file = benchmark_run_dir / "tm" / "tm.pid"
        try:
            pid_str = ltm_pid_file.read_text()
        except FileNotFoundError:
            pass
        else:
            ltm_pid = int(pid_str)
            logger.debug("waiting for local tool-meister (%d) to exit", ltm_pid)
            wait_for_pid(ltm_pid)
    except Exception:
        logger.exception("Exception encountered waiting for local tool-meister")
        ret_val = 1

    # All was good so far, so we can terminate the redis server.
    try:
        ret_val = redis_server.kill(ret_val)
    except Exception:
        logger.exception("Exception encountered terminating Redis server")
        ret_val = 1

    return ret_val


def start(_prog: str, cli_params: Namespace) -> int:
    """Main program for the tool meister stop CLI interface.

    Stopping the Tool Meisters involves four steps:

    1. End ("end") the run of the persistent tools

    2. Collect any requested system configuration information ("sysinfo")

    3. Sends the "terminate" message to the redis server so that all connected
    services, tool-meisters, tool-data-sink, etc. will shutdown.  Once all
    services acknowledge the receipt of the "terminate" message, we look to
    ensure that the local Tool Data Sink and optional Tool Meister instance
    have shutdown by verifying their recorded pids are no longer seen on the
    local host.

    :cli_params: expects a CLI parameters object which has three attributes:

        * tool_group - The tool group from which to load the registered tools
        * interrupt  - True / False value indicating if the call to stop the
                       Tool Meisters is in response to an interrupt or not
        * sysinfo    - The system information set to be collected at the start

    Return 0 on success, 1 on failure.
    """
    prog = Path(_prog)
    logger = logging.getLogger(prog.name)
    if os.environ.get("_PBENCH_TOOL_MEISTER_STOP_LOG_LEVEL") == "debug":
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logger.setLevel(log_level)
    sh = logging.StreamHandler()
    sh.setLevel(log_level)
    shf = logging.Formatter(f"{prog.name}: %(message)s")
    sh.setFormatter(shf)
    logger.addHandler(sh)

    try:
        ToolGroup.verify_tool_group(cli_params.tool_group)
    except BadToolGroup as exc:
        logger.error(str(exc))
        return 1
    else:
        group = cli_params.tool_group

    sysinfo, bad_l = cli_verify_sysinfo(cli_params.sysinfo)
    if bad_l:
        logger.error('invalid sysinfo option(s), "{}"', ",".join(bad_l))

    interrupt = cli_params.interrupt
    if interrupt and sysinfo:
        # Don't collect system information if the CLI invocation specified an
        # interrupt occured.
        logger.warning("system information not collected when --interrupt specified")
        sysinfo = ""

    try:
        full_hostname = os.environ["_pbench_full_hostname"]
        benchmark_run_dir = Path(os.environ["benchmark_run_dir"]).resolve(strict=True)
    except Exception:
        logger.exception("failed to fetch required parameters from the environment")
        return 1

    try:
        redis_server = RedisServer(
            cli_params.redis_server, benchmark_run_dir, full_hostname
        )
    except RedisServer.Err as exc:
        logger.error(str(exc))
        return exc.return_code

    # The Redis server is always running on the local host with the CLI.
    with Client(
        redis_host=redis_server.host,
        redis_port=redis_server.port,
        channel_prefix=cli_tm_channel_prefix,
        logger=logger,
    ) as client:
        # First we end the persistent tools
        tool_dir = benchmark_run_dir / f"tools-{group}"
        try:
            tool_dir.mkdir(exist_ok=True)
        except Exception as exc:
            error_log(f"failed to create tool output directory, '{tool_dir}': {exc}")
            end_ret_val = 1
        else:
            end_ret_val = client.publish(group, tool_dir, "end", None)

        # Next we collect the system configuration information only if we were
        # successfully able to end the persistent tools run.
        if end_ret_val == 0 and sysinfo:
            sysinfo_path = benchmark_run_dir / "sysinfo" / "end"
            try:
                sysinfo_path.mkdir(parents=True)
            except Exception:
                error_log(
                    f"Unable to create sysinfo-dump directory base path: {sysinfo_path}",
                )
            else:
                msg = "Collecting system information"
                print(msg)
                info_log(msg)
                # We don't check the return status for the sysinfo operation
                # since the publish() method will log errors for us, and its
                # success or failure does not affect the return status of
                # stopping the Tool Meister sub-system.
                client.publish(group, sysinfo_path, "sysinfo", sysinfo)

        # Finally we terminate the running Tool Data Sinks and the Tool
        # Meisters, indicating if this termination is due to an interruption.
        # Note that we always issue the
        term_ret_val = client.terminate(group, interrupt)

    # If the "end" persistent tools operation failed, we want to be sure that
    # this command returns an error status unless running with --interrupt.
    # "pbench-tool-meister-stop --interrupt" may occur in any TM state (e.g.,
    # actively "running"), in which case "end" will be rejected. We won't fail
    # the stop command because of this, since the point is to terminate as
    # gracefully and quickly as possible.
    #
    # If the "end" succeeded, or if we're in interrupt mode, return the status
    # of the terminate operation instead.
    ret_val = end_ret_val if (end_ret_val != 0 and not interrupt) else term_ret_val

    if redis_server.locally_managed():
        # The client operations have finished, successful or unsuccessfully,
        # and we were not given an explicit Redis server to use.  So the
        # previous pbench-tool-meister-start must have set up the local Tool
        # Data Sink, Tool Meister (if registered), and the Redis server.  It is
        # our responsibility to make sure these processes shut down correctly.
        shutdown_ret_val = graceful_shutdown(benchmark_run_dir, redis_server, logger)
        if ret_val == 0:
            # If client termination was successful, report the status of the
            # graceful shutdown of the Tool Data Sink and the Redis server.
            ret_val = shutdown_ret_val

    return ret_val


_NAME_ = "pbench-tool-meister-stop"


def main():
    parser = ArgumentParser(f"{_NAME_} [--sysinfo <list of system information items>]")
    parser.add_argument(
        "--sysinfo",
        default=None,
        help="The list of system information items to be collected.",
    )
    parser.add_argument(
        "--interrupt",
        action="store_true",
        help="Whether or not the stop operation is in response to an interrupt.",
    )
    parser.add_argument(
        "--redis-server",
        dest="redis_server",
        default=os.environ.get("PBENCH_REDIS_SERVER", None),
        help=(
            "Use an existing Redis server specified by <hostname>:<port>;"
            " implies the use of an existing Tool Data Sink and Tool Meisters"
            " as well."
        ),
    )
    parser.add_argument(
        "tool_group",
        help="The tool group name of tools being run in the Tool Meisters.",
    )
    parsed = parser.parse_args()
    return start(sys.argv[0], parsed)
