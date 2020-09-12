import inspect
import os
from pathlib import Path
import sys

import click

from pbench.agent.utils import setup_logging
from pbench.agent.meister.base import MeisterCommand
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options

NAME = os.path.basename(sys.argv[0])


class Process(MeisterCommand):
    def __init__(self, context):
        super(Process, self).__init__(context)

        # FIXME: move to common area
        self.redis_host = "localhost"
        # Port number is "One Tool" in hex 0x17001
        self.redis_port = 17001

        # FIXME: this should be moved to a shared area
        self.tm_channel = "tool-meister-chan"
        self.cl_channel = "tool-meister-client"

        # List of allowed actions
        self.allowed_actions = ("start", "stop", "send", "kill")

        self.logger = setup_logging(name=NAME, logfile=self.pbench_log)

        tool_group_dir = self.tool_group_dir(self.context.group)
        if not tool_group_dir.exists():
            sys.exit(1)
        
        if self.context.action == "kill":
            self.logger.info("pbench-kill-tools is a no-op and has been deprecated: pbench-stop-tools ensures tools are properly cleaned up.")
            sys.exit(0)
        tool_output_dir = Path(self.context.directory, f"tools-{self.context.group}")
        if self.context.action == "start":
            tool_output_dir.mkdir(parents=True, exist_ok=True)
            if not tool_output_dir.exists():
                self.logger.error(f"[{NAME}] failed to create tool output directory, {tool_output_dir}")
                sys.exit(1)
        else:
            if not tool_output_dir.exists():
                self.logger.error(f"[{NAME}] expected tool output directory, {tool_output_dir}, does not exist")
                sys.exit(1)
        
        self.context.directory = str(tool_output_dir)

    def execute(self):
        return self.client()

def group_option(f):
    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.group = value
        return value

    return click.option(
       "-g", "--group", default="default", required=True, callback=callback, expose_value=False,
    )(f)


def directory_option(f):
    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.directory = value
        return value

    return click.option(
        "-g", "--dir", required=True, callback=callback, expose_value=False,
    )(f)

@click.command(help="")
@common_options
@group_option
@directory_option
@pass_cli_context
def send(ctxt):
    ctxt.action = inspect.stack()[0][3]
    status = Process(ctxt).execute()
    sys.exit(status)

@click.command(help="")
@common_options
@group_option
@directory_option
@pass_cli_context
def stop(ctxt):
    ctxt.action = inspect.stack()[0][3]
    status = Process(ctxt).execute()
    sys.exit(status)

@click.command(help="")
@common_options
@group_option
@directory_option
@pass_cli_context
def start(ctxt):
    ctxt.action = inspect.stack()[0][3]
    status = Process(ctxt).execute()
    sys.exit(status)

@click.command(help="")
@common_options
@group_option
@directory_option
@pass_cli_context
def kill(ctxt):
    ctxt.action = inspect.stack()[0][3]
    status = Process(ctxt).execute()
    sys.exit(status)