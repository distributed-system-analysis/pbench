import click

from pbench import BadConfig
from pbench.cli import pass_cli_context
from pbench.cli.server import config_setup
from pbench.cli.server.options import common_options
from pbench.server.database.models.users import User

USER_LIST_ROW_FORMAT = "{0:15}\t{1:36}"
USER_LIST_HEADER_ROW = USER_LIST_ROW_FORMAT.format("Username", "OIDC ID")


@click.group("user_group")
@click.version_option()
@pass_cli_context
@common_options
def user_command_cli(context):
    # Entry point
    pass


# Users list CLI
@user_command_cli.command()
@common_options
@pass_cli_context
def user_list(context: object) -> None:
    try:
        config_setup(context)
        click.echo(USER_LIST_HEADER_ROW)

        # Query all the users
        users = User.query_all()

        for user in users:
            click.echo(USER_LIST_ROW_FORMAT.format(user.username, user.id))

        rv = 0
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)
