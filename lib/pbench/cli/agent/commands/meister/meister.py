# -*- mode: python -*-

"""pbench-tool-meister

Handles the life-cycle executing a given tool on a host. The tool meister
performs the following operations:

  1. Ensures the given tool exists with the supported version
  2. Fetches the parameters configured for the tool
  3. Waits for the message to start the tool
     a. Messages contain three pieces of information:
        the next operational state to move to, the tool group being for which
        the operation will be applied, and the directory in which the tool-
        data-sink will collect and store all the tool data during send
        operations
  4. Waits for the message to stop the tool
  5. Waits for the message to send the tool data remotely
  6. Repeats steps 3 - 5 until a "terminate" message is received

If a SIGTERM or SIGQUIT signal is sent to the tool meister, any existing
running tool is shutdown, all local data is removed, and the tool meister
exits.

A redis [1] instance is used as the communication mechanism between the
various tool meisters on nodes and the benchmark driver. The redis instance is
used both to communicate the initial data set describing the tools to use, and
their parameteres, for each tool meister, as well as a pub/sub for
coordinating starts and stops of all the tools.

The tool meister is given two arguments when started: the redis server to use,
and the redis key to fetch its configuration from for its operation.

[1] https://redis.io/

$ sudo dnf install python3-redis
$ sudo pip3 install python-daemon
$ sudo pip3 install python-pidfile
"""

import json
import logging
import os
import sys

import click
import daemon
import pidfile
import redis

from pbench.agent.meister import Terminate, ToolMeister
from pbench.cli.agent import CliContext, pass_cli_context


def _redis_host(f):
    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.redis_host = value
        return value

    return click.argument(
        "redis_host", required=True, callback=callback, expose_value=False,
    )(f)


def _redis_port(f):
    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.redis_port = value
        return value

    return click.argument(
        "redis_port", required=True, callback=callback, expose_value=False,
    )(f)


def _param_key(f):
    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.param_key = value
        return value

    return click.argument(
        "param_key", required=True, callback=callback, expose_value=False,
    )(f)


@click.command(help="")
@_redis_host
@_redis_port
@_param_key
@pass_cli_context
def main(ctxt):
    """Main program for the Tool Meister.

    This function is the simple driver for the tool meister behaviors,
    handling argument processing, logging setup, initial connection to
    Redis(), fetch and validation of operational paramters from Redis(), and
    then the daemonization of the ToolMeister operation.

    Arguments:  argv - a list of parameters

    Returns 0 on success, > 0 when an error occurs.

    """
    PROG = os.path.basename(sys.argv[0])
    pbench_bin = os.environ["pbench_install_dir"]

    logger = logging.getLogger(PROG)
    fh = logging.FileHandler(f"{ctxt.param_key}.log")
    if os.environ.get("_PBENCH_UNIT_TESTS"):
        fmtstr = "%(levelname)s %(name)s %(funcName)s -- %(message)s"
    else:
        fmtstr = (
            "%(asctime)s %(levelname)s %(process)s %(thread)s"
            " %(name)s %(funcName)s %(lineno)d -- %(message)s"
        )
    fhf = logging.Formatter(fmtstr)
    fh.setFormatter(fhf)
    if os.environ.get("_PBENCH_TOOL_MEISTER_LOG_LEVEL") == "debug":
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    fh.setLevel(log_level)
    logger.addHandler(fh)
    logger.setLevel(log_level)

    try:
        redis_server = redis.Redis(host=ctxt.redis_host, port=ctxt.redis_port, db=0)
    except Exception as e:
        logger.error(
            "Unable to construct Redis client, %s:%s: %s",
            ctxt.redis_host,
            ctxt.redis_port,
            e,
        )
        return 3

    try:
        params_raw = redis_server.get(ctxt.param_key)
        if params_raw is None:
            logger.error('Parameter key, "%s" does not exist.', ctxt.param_key)
            return 4
        logger.info("params_key (%s): %r", ctxt.param_key, params_raw)
        params_str = params_raw.decode("utf-8")
        params = json.loads(params_str)
        # Validate the tool meister parameters without constructing an object
        # just yet, as we want to make sure we can talk to the redis server
        # before we go through the trouble of daemonizing below.
        ToolMeister.fetch_params(params)
    except Exception as exc:
        logger.error(
            "Unable to fetch and decode parameter key, '%s': %s", ctxt.param_key, exc
        )
        return 5
    else:
        redis_server.connection_pool.disconnect()
        del redis_server

    # Before we daemonize, flush any data written to stdout or stderr.
    sys.stderr.flush()
    sys.stdout.flush()

    ret_val = 0
    pidfile_name = f"{ctxt.param_key}.pid"
    pfctx = pidfile.PIDFile(pidfile_name)
    with open(f"{ctxt.param_key}.out", "w") as sofp, open(
        f"{ctxt.param_key}.err", "w"
    ) as sefp, daemon.DaemonContext(
        stdout=sofp,
        stderr=sefp,
        working_directory=os.getcwd(),
        umask=0o022,
        pidfile=pfctx,
        files_preserve=[fh.stream.fileno()],
    ):
        try:
            # Previously we validated the tool meister parameters, and in
            # doing so made sure we had proper access to the redis server.
            #
            # We can safely create the ToolMeister object now that we are
            # "daemonized".
            logger.debug("constructing Redis() object")
            try:
                # NOTE: we have to recreate the connection to the redis
                # service since all open file descriptors were closed as part
                # of the daemonizing process.
                redis_server = redis.Redis(
                    host=ctxt.redis_host, port=ctxt.redis_port, db=0
                )
            except Exception as e:
                logger.error(
                    "Unable to connect to redis server, %s:%s: %s",
                    ctxt.redis_host,
                    ctxt.redis_port,
                    e,
                )
                return 6
            else:
                logger.debug("constructed Redis() object")

            # FIXME: we should establish signal handlers that do the following:
            #   a. handle graceful termination (TERM, INT, QUIT)
            #   b. log operational state (HUP maybe?)

            try:
                tm = ToolMeister(pbench_bin, params, redis_server, logger)
            except Exception:
                logger.exception(
                    "Unable to construct the ToolMeister object with params, %r",
                    params,
                )
                return 7

            terminate = False
            try:
                while not terminate:
                    try:
                        logger.debug("waiting ...")
                        action, data = tm.wait_for_command()
                        logger.debug("acting ... %r, %r", action, data)
                        failures = action(data)
                        if failures > 0:
                            logger.warning(
                                "%d failures encountered for action, %r,"
                                " on data, %r",
                                failures,
                                action,
                                data,
                            )
                    except Terminate:
                        logger.info("terminating")
                        terminate = True
            except Exception:
                logger.exception("Unexpected error encountered")
                ret_val = 8
            finally:
                tm.cleanup()
        finally:
            logger.info("Remove pid file ... (%s)", pidfile_name)
            try:
                os.unlink(pidfile_name)
            except Exception:
                logger.exception("Failed to remove pid file %s", pidfile_name)

    return ret_val
