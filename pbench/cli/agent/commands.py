import click

from pbench.cli.agent.cleanup import PbenchCleanup


@click.command()
def cleanup():
    PbenchCleanup().main()
