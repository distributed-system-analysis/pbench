import os
import pathlib
import sys

import logging

import click
import colorlog

from pbench.lib.agent.config import AgentConfig

# Get the name of the program that is running so
# we can have better log messages
logger = logging.getLogger(os.path.basename(sys.argv[0]))

pbench_log = AgentConfig().logdir
tmp_log_file = pathlib.Path("/tmp") / "pbench.log"
if pbench_log is None:
    click.echo("Log file is not configured falling back to /tmp for logging")
    pbench_log = tmp_log_file
try:
    fh = logging.FileHandler(pbench_log)
except (OSError, IOError):
    click.echo(
        "log file is not writable or accessable, falling back to /tmp/ for logging"
    )
    fh = logging.FileHandler(tmp_log_file)

if os.environ.get("_PBENCH_BENCH_TESTS"):
    fmtstr = "%(levelname)s %(name)s %(funcName)s -- %(message)s"
else:
    fmtstr = (
        "%(asctime)s %(levelname)s %(process)s %(thread)s"
        " %(name)s %(funcName)s %(lineno)d -- %(message)s"
    )
fhf = logging.Formatter(fmtstr)
fh.setFormatter(fhf)
fh.setLevel(logging.INFO)
logger.addHandler(fh)
logger.setLevel(logging.INFO)

logger_formatter = colorlog.ColoredFormatter(
    "%(log_color)s %(levelname)s %(process)s %(thread)s"
    " %(name)s %(funcName)s %(lineno)d -- %(message)s",
    log_colors=dict(
        DEBUG="blue",
        INFO="green",
        WARNING="yellow",
        ERROR="red",
        CRITICAL="bold_red,bg_white",
    ),
)
# Create stream handler with debug level

sh = logging.StreamHandler()
sh.setLevel(logging.INFO)

# Add the logger_formatter to sh
sh.setFormatter(logger_formatter)

# Create logger and add handler to it
logger.addHandler(sh)
