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

import sys

import click

from pbench.agent.meister.base import MeisterCommand
from pbench.cli.agent import CliContext, pass_cli_context


class Meister(MeisterCommand):
    def __init__(self, context):
        super(Meister, self).__init__(context)

    def execute(self):
        return self.meister()


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
    status = Meister(ctxt).execute()
    sys.exit(status)
