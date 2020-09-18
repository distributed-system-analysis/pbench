import click

from pbench.cli.agent.commands.log import add_metalog_option


@click.command()
@click.argument("lfile")
@click.argument("section")
@click.argument("option")
def main(lfile, section, option):
    add_metalog_option(lfile, section, option)
