import datetime

import click

from pbench import BadConfig
from pbench.cli import pass_cli_context
from pbench.cli.server import config_setup
from pbench.cli.server.options import common_options
from pbench.server.database.models.users import Roles, User

USER_LIST_ROW_FORMAT = "{0:15}\t{1:15}"
USER_LIST_HEADER_ROW = USER_LIST_ROW_FORMAT.format("Username", "oidc id")


# User create CLI
@click.group("user_group")
@click.version_option()
@pass_cli_context
@common_options
def user_command_cli(context):
    # Entry point
    pass


@user_command_cli.command()
@pass_cli_context
@click.option(
    "--username",
    prompt=True,
    required=True,
    help="pbench server account username (will prompt if unspecified)",
)
@click.option(
    "--oidc-id",
    prompt=True,
    required=True,
    help="OIDC server user id (will prompt if unspecified)",
)
@click.option(
    "--email",
    prompt=True,
    required=True,
    help="pbench server account email (will prompt if unspecified)",
)
@click.option(
    "--first-name",
    required=False,
    help="pbench server account first name (will prompt if unspecified)",
)
@click.option(
    "--last-name",
    required=False,
    help="pbench server account last name (will prompt if unspecified)",
)
@click.option(
    "--role",
    type=click.Choice([role.name for role in Roles], case_sensitive=False),
    required=False,
    help="Optional role of the user such as Admin",
)
@common_options
def user_create(
    context: object,
    username: str,
    oidc_id: str,
    email: str,
    first_name: str,
    last_name: str,
    role: str,
) -> None:
    try:
        config_setup(context)
        user = User(
            username=username,
            oidc_id=oidc_id,
            profile={
                "user": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                },
                "server": {
                    "roles": [role] if role else [],
                    "registered_on": datetime.datetime.now().strftime(
                        "%m/%d/%Y, %H:%M:%S"
                    ),
                },
            },
        )
        user.add()
        if user.is_admin():
            click.echo(f"Admin user {username} registered")
        else:
            click.echo(f"User {username} registered")
        rv = 0
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)


# User delete CLI
@user_command_cli.command()
@common_options
@click.argument("username")
@pass_cli_context
def user_delete(context: object, username: str) -> None:
    try:
        # Delete the the user with specified username
        user = User.query(username=username)
        config_setup(context)
        if not user:
            click.echo(f"User {username} does not exist", err=True)
            rv = 1
        else:
            user.delete()
            rv = 0
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)


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
            click.echo(
                USER_LIST_ROW_FORMAT.format(
                    user.username,
                    user.oidc_id,
                )
            )

        rv = 0
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)


# User update CLI
@user_command_cli.command()
@common_options
@click.argument("updateuser")
@click.option(
    "--email",
    required=False,
    help="Specify the new email",
)
@click.option(
    "--first-name",
    required=False,
    help="Specify the new first name",
)
@click.option(
    "--last-name",
    required=False,
    help="Specify the new last name",
)
@click.option(
    "--role",
    required=False,
    type=click.Choice([role.name for role in Roles], case_sensitive=False),
    help="Specify the new role",
)
@pass_cli_context
def user_update(
    context: object,
    updateuser: str,
    first_name: str,
    last_name: str,
    email: str,
    role: str,
) -> None:
    try:
        config_setup(context)
        # Query the user
        user = User.query(username=updateuser)

        if user is None:
            click.echo(f"User {updateuser} doesn't exist")
            rv = 1
        else:
            dict_to_update = {}
            user_fields = {}
            server_fields = {}
            if first_name:
                user_fields["first_name"] = first_name

            if last_name:
                user_fields["last_name"] = last_name

            if email:
                user_fields["email"] = email

            if role:
                server_fields["role"] = [role]

            if user_fields:
                dict_to_update["user"] = user_fields
            if server_fields:
                dict_to_update["server"] = server_fields

            # Update the user
            user.update(new_profile=dict_to_update)

            click.echo(f"User {updateuser} updated")
            rv = 0
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)
