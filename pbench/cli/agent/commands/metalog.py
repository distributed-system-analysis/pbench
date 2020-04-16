import click

from pbench.agent.task.add_metalog_option import add_metalog_option

#
# pbench cli
#
@click.group()
@click.pass_context
def metalog(ctx):
    """Used for passing the context from the main cli"""
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
# pbench backwards compatible
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
