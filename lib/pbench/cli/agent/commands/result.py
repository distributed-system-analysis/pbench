import shutil

import click

from pbench.agent.config import AgentConfig
from pbench.agent.utils import initialize
from pbench.agent.utils.fs import find_dirs
from pbench.cli import options


@click.group(help="move results")
@click.pass_context
def results(ctxt):
    """Place holder for pbench-cli config subcomand"""
    pass


@click.command(help="delete all benchmark results")
@click.pass_context
@options.pbench_agent_config
def clear(debug, config):
    c = AgentConfig(config)

    initialize(c)
    rundir = c.rundir
    if rundir.exists():
        dirs = find_dirs("tmp", rundir) + find_dirs("tools-*", rundir)
        for d in dirs:
            shutil.rmtree(d)


results.add_command(clear)
