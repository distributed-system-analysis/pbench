import click

from pbench.cli.agent import options

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
@options.pbench_upload_user
@options.pbench_server_prefix
@options.pbench_show_server
def move(user, prefix, show_server):
    move_results(user, prefix, show_server)


#
# pbench backwards compat
#
@click.command()
@options.pbench_upload_user
@options.pbench_server_prefix
@options.pbench_show_server
def _move_results(user, prefix, show_server):
    move_results(user, prefix, show_server)
