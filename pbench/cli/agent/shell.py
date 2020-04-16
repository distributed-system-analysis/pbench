import click

from pbench.cli.agent.commands import metalog
from pbench.cli.agent.commands import results


@click.group()
@click.pass_context
def main(ctx):
    """Pass the main args, (that we might have in the future)"""
    ctx.obj = {}
    ctx.obj["args"] = {}
    return 0


main.add_command(metalog.metalog)
main.add_command(results.results)
