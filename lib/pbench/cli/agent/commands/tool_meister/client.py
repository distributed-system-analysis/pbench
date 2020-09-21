# -*- mode: python -*-

"""pbench-tool-meister-client

Responsible for publishing the requested tool meister action.  The
actions can be one of "start", "stop", or "send".
"""

import sys

import click

from pbench.agent.tool_meister.base import MeisterCommand
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


class Client(MeisterCommand):
    def __init__(self, context):
        super().__init__(context)

        # FIXME: move to common area
        self.redis_host = "localhost"
        # Port number is "One Tool" in hex 0x17001
        self.redis_port = 17001

        # FIXME: this should be moved to a shared area
        self.tm_channel = "tool-meister-chan"
        self.cl_channel = "tool-meister-client"

        # List of allowed actions
        self.allowed_actions = ("start", "stop", "send", "kill")

    def execute(self):
        return self.client()


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
@common_options
@group_option
@directory_option
@action_option
@pass_cli_context
def main(ctxt):
    """Main program for the tool meister client."""
    status = Client(ctxt).execute()
    sys.exit(status)
