import click

from pbench.agent import utils
from pbench.cli.agent import options
from pbench.cli.agent.commands.log import add_metalog_option
from pbench.cli.agent.commands.results import move_results


#
# log subcommand
#
@click.group()
@click.pass_context
# Used for passing the context from the main cli
def metalog(ctx):
    pass


@metalog.group()
@click.argument("logfile")
@click.argument("section")
@click.argument("option")
@click.argument("value")
def metalog_add_option(logfile, section, option, value):
    """Add an option to a section of the metadata.log file.

    E.g. using an 'iterations' arg for the option
    iterations: 1-iter, 2-iter, 3-iter
    where the iterations are in the <iterations.file>, one iteration per line
    """
    add_metalog_option(logfile, section, option, value)


#
# results subcommand
#
@click.group()
@click.pass_context
# Used for passing the context from the main cli
def results(ctx):
    pass


@results.command()
@options.pbench_upload_user
@options.pbench_server_prefix
@options.pbench_show_server
def move(user, prefix, show_server):
    move_results(user, prefix, show_server)


@click.group()
@click.pass_context
@options.pbench_agent_config
@options.pbench_agent_debug
def main(ctx, config, debug):
    """Pass the main args, (that we might have in the future)"""
    ctx = utils.init_context(ctx, config, debug)
    return 0


main.add_command(metalog)
main.add_command(results)
