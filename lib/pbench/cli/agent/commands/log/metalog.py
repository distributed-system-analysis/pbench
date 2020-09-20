from configparser import ConfigParser, NoSectionError
import sys

import click


@click.command()
@click.argument("lfile")
@click.argument("section")
@click.argument("option")
def main(lfile, section, option):
    config = ConfigParser()
    config.read(lfile)
    # python3
    # config[section][option] = ', '.join(sys.stdin.read().split())
    sin = sys.stdin.read().replace("%", "%%")
    try:
        config.set(section, option, ", ".join(sin.split()))
    except NoSectionError:
        config.add_section(section)
        config.set(section, option, ", ".join(sin.split()))
    config.write(open(lfile, "w"))
