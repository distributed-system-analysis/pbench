import click
from pbench import BadConfig
from pbench.server import PbenchServerConfig
from pbench.cli.server import pass_cli_context
from pbench.cli.server.options import common_options
from pbench.common.logger import get_pbench_logger
from pbench.server.database.models.users import User
from pbench.server.database.database import Database

_NAME_ = "pbench-user-create"


class UserCreate:
    def __init__(self, context):
        self.context = context

    def execute(self):
        config = PbenchServerConfig(self.context.config)

        logger = get_pbench_logger(_NAME_, config)

        # We're going to need the Postgres DB to track dataset state, so setup
        # DB access.
        Database.init_db(config, logger)

        user = User(
            username=self.context.username,
            password=self.context.password,
            first_name=self.context.first_name,
            last_name=self.context.last_name,
            email=self.context.email,
        )
        user.add()
        click.echo(f"User {self.context.username} registered")


@click.command()
@common_options
@click.option(
    "--username",
    prompt=True,
    required=True,
    help="pbench server account username (will prompt if unspecified)",
)
@click.option(
    "--password",
    prompt=True,
    hide_input=True,
    required=True,
    help="pbench server account password (will prompt if unspecified)",
)
@click.option(
    "--email",
    prompt=True,
    required=True,
    help="pbench server account email (will prompt if unspecified)",
)
@click.option(
    "--first-name",
    prompt=True,
    required=True,
    help="pbench server account first name (will prompt if unspecified)",
)
@click.option(
    "--last-name",
    prompt=True,
    required=True,
    help="pbench server account last name (will prompt if unspecified)",
)
@pass_cli_context
def main(context, username, password, email, first_name, last_name):
    context.username = username
    context.password = password
    context.email = email
    context.first_name = first_name
    context.last_name = last_name

    try:
        rv = UserCreate(context).execute()
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)
