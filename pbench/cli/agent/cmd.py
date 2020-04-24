import click

from pbench.cli import options
from pbench.cli.agent.commmands.log import add_metalog_option
from pbench.cli.agent.commands.results import move_results

#
# pbench-add-metalog
#
@click.command()
@click.argument("logfile")
@click.argument("section")
@click.argument("option")
@click.argument("value")
def metalog_add(logfile, section, option, value):
    """Add an option to a section of the metadata.log file.

    E.g. using an 'iterations' arg for the option
    iterations: 1-iter, 2-iter, 3-iter
    where the iterations are in the <iterations.file>, one iteration per line
    """
    add_metalog_option(logfile, section, option, value)


#
# pbench-move-results
#
#
# pbench backwards compat
#
@click.command()
@options.pbench_upload_user
@options.pbench_server_prefix
@options.pbench_show_server
def _move_results(user, prefix, show_server):
    move_results(user, prefix, show_server)
