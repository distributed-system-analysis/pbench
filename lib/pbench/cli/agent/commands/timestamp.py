"""pbench-log-timestamp"""

import time

import click


@click.command()
def main():
    """ Add timestamp to user input"""
    stdin = click.get_text_stream("stdin").read()
    for line in stdin.splitlines():
        print(f"{time.time_ns()}:{line}")
