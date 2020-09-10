# -*- mode: python -*-

"""pbench-tool-meister-client

Responsible for publishing the requested tool meister action.  The
actions can be one of "start", "stop", or "send".
"""

import json
import logging
import os
import sys

import click
import redis

from pbench.cli.agent import CliContext, pass_cli_context

# FIXME: move to common area
redis_host = "localhost"
# Port number is "One Tool" in hex 0x17001
redis_port = 17001

# FIXME: this should be moved to a shared area
tm_channel = "tool-meister-chan"
cl_channel = "tool-meister-client"

# List of allowed actions
allowed_actions = ("start", "stop", "send", "kill")


def group_option(f):
    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.group = value
        return value

    return click.argument(
        "group", required=True, callback=callback, expose_value=False,
    )(f)


def directory_option(f):
    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.directory = value
        return value

    return click.argument(
        "directory", required=True, callback=callback, expose_value=False,
    )(f)


def action_option(f):
    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.action = value
        return value

    return click.argument(
        "operation", required=True, callback=callback, expose_value=False,
    )(f)


@click.command(help="")
@group_option
@directory_option
@action_option
@pass_cli_context
def main(ctxt):
    """Main program for the tool meister client."""
    PROG = os.path.basename(sys.argv[0])
    logger = logging.getLogger(PROG)

    if os.environ.get("_PBENCH_TOOL_MEISTER_CLIENT_LOG_LEVEL") == "debug":
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logger.setLevel(log_level)
    sh = logging.StreamHandler()
    sh.setLevel(log_level)
    shf = logging.Formatter("%(message)s")
    sh.setFormatter(shf)
    logger.addHandler(sh)

    if ctxt.action not in allowed_actions:
        raise Exception(
            f"Unrecognized action, '{ctxt.action}', allowed actions are:"
            f" {allowed_actions}"
        )
    elif ctxt.action == "kill":
        # FIXME: we need to implement the gritty method of killing all the
        # tool meisters, locally and remotely, and ensuring they are all
        # properly shut down.
        return 0

    logger.debug("constructing Redis() object")
    try:
        redis_server = redis.Redis(host=redis_host, port=redis_port, db=0)
    except Exception as e:
        logger.error(
            "Unable to connect to redis server, %s:%s: %s", redis_host, redis_port, e
        )
        return 2
    else:
        logger.debug("constructed Redis() object")

    logger.debug("Redis().get('tm-pids')")
    try:
        tm_pids_raw = redis_server.get("tm-pids")
        if tm_pids_raw is None:
            logger.error('Tool Meister PIDs key, "tm-pids", does not exist.')
            return 3
        tm_pids_str = tm_pids_raw.decode("utf-8")
        tm_pids = json.loads(tm_pids_str)
    except Exception as ex:
        logger.error('Unable to fetch and decode "tm-pids" key: %s', ex)
        return 4
    else:
        logger.debug("Redis().get('tm-pids') success")
        expected_pids = 0
        tracking = {}
        try:
            tracking["ds"] = tm_pids["ds"]
        except Exception:
            logger.error("missing data sink in 'tm-pids', %r", tm_pids)
            return 5
        else:
            expected_pids += 1
            tracking["ds"]["status"] = None
        try:
            tms = tm_pids["tm"]
        except Exception:
            logger.error("missing tool meisters in 'tm-pids', %r", tm_pids)
            return 6
        else:
            expected_pids += len(tms)
            for tm in tms:
                tm["status"] = None
                tracking[tm["hostname"]] = tm
            logger.debug("tm_pids = %r", tm_pids)

    # First setup our client channel for receiving action completion statuses.
    logger.debug("pubsub")
    pubsub = redis_server.pubsub()
    logger.debug("subscribe")
    pubsub.subscribe(cl_channel)
    logger.debug("listen")
    client_chan = pubsub.listen()
    logger.debug("next")
    resp = next(client_chan)
    assert resp["type"] == "subscribe", f"Unexpected 'type': {resp!r}"
    assert resp["pattern"] is None, f"Unexpected 'pattern': {resp!r}"
    assert (
        resp["channel"].decode("utf-8") == cl_channel
    ), f"Unexpected 'channel': {resp!r}"
    assert resp["data"] == 1, f"Unexpected 'data': {resp!r}"
    logger.debug("next success")

    # The published message contains three pieces of information:
    #   {
    #     "action": "< 'start' | 'stop' | 'send' | 'kill' >",
    #     "group": "< the tool group name for the tools to operate on >",
    #     "directory": "< the local directory path to store collected data >"
    #   }
    # The caller of tool-meister-client must be sure the directory argument
    # is accessible by the tool-data-sink.
    logger.debug("publish %s", tm_channel)
    msg = dict(action=ctxt.action, group=ctxt.group, directory=ctxt.directory)
    try:
        num_present = redis_server.publish(tm_channel, json.dumps(msg))
    except Exception:
        logger.exception("Failed to publish client message")
        ret_val = 1
    else:
        logger.debug("published %s", tm_channel)
        if num_present != expected_pids:
            logger.error(
                "Failed to publish to %d pids, only encountered %d on the channel",
                expected_pids,
                num_present,
            )
            ret_val = 1
        else:
            ret_val = 0

    # Wait for an operational status message from the number of tool meisters
    # listening (and tool data sink), saying that the message was received and
    # operated on successfully.
    #
    # FIXME: we need some sort of circuit breaker when we lose a Tool Meister
    # or Data Sink for some reason *after* they have received the message
    # (num_present will never be reached).
    done_count = 0
    while done_count < num_present:
        logger.debug("next")
        try:
            resp = next(client_chan)
        except Exception:
            logger.exception("Error encountered waiting for status reports")
            ret_val = 1
            break
        else:
            logger.debug("next success")
        try:
            json_str = resp["data"].decode("utf-8")
            data = json.loads(json_str)
        except Exception:
            logger.error("data payload in message not JSON, %r", json_str)
            ret_val = 1
        else:
            try:
                kind = data["kind"]
                hostname = data["hostname"]
                status = data["status"]
            except Exception:
                logger.error("unrecognized status payload, %r", json_str)
                ret_val = 1
            else:
                if kind == "ds":
                    assert hostname != "ds", f"Logic Bomb! FIXME"
                    hostname = "ds"
                else:
                    if hostname not in tracking:
                        logger.warning(
                            "encountered hostname not being tracked, %r", json_str
                        )
                        ret_val = 1
                        continue
                tracking[hostname]["status"] = status
                if status != "success":
                    logger.warning(
                        "Host '%s' status message not successful: '%s'",
                        hostname,
                        status,
                    )
                    ret_val = 1
                done_count += 1

    logger.debug("unsubscribe")
    pubsub.unsubscribe()
    logger.debug("pubsub close")
    pubsub.close()

    return ret_val
