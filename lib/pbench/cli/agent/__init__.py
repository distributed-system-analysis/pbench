import click


class CliContext:
    """Inialize an empty click object"""

    pass


pass_cli_context = click.make_pass_decorator(CliContext, ensure=True)
