import sys

import click


def init_context(context, config, debug):
    context.obj = {}
    context.obj["args"] = {}
    context.obj["args"]["config"] = config
    context.obj["args"]["debug"] = debug
    return context


def error_out(msg):
    click.secho(msg, fg="red")
    sys.exit(1)


def error_warn(msg):
    click.secho(msg, fg="yellow")


def error_info(msg):
    click.secho(msg, fg="green")


def error_debug(msg):
    click.secho(msg, fg="blue")
