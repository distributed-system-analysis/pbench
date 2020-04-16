import click

from pbench.agent.task.move_results import move_results

#
# pbench-cli
#
@click.group()
@click.pass_context
def results(ctx):
    """Used for passing the context from the main cli"""
    pass


@results.command()
@click.option(
    "-u", "--user", "user", default="", help="Specify username for server upload"
)
@click.option("-p", "--prefix", default="", help="Specify a prefix for server upload")
@click.option(
    "-S", "--show-server", required=False, help="Show server",
)
def move(user, prefix, show_server):
    move_results(user, prefix, show_server)


#
# pbench backwards compat
#
@click.command()
@click.option(
    "-u", "--user", "user", default="", help="Specify username for server upload"
)
@click.option("-p", "--prefix", default="", help="Specify a prefix for server upload")
@click.option(
    "-S", "--show-server", required=False, help="Show server",
)
def _move_results(user, prefix, show_server):
    move_results(user, prefix, show_server)
