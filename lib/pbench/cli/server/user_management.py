import click

from pbench import BadConfig
from pbench.cli.server import config_setup, pass_cli_context
from pbench.cli.server.options import common_options
from pbench.server.database.database import Database
from pbench.server.database.models.users import User


# User create CLI
@click.group("user_group")
@click.version_option()
@pass_cli_context
def cli(ctx):
    pass  # Entry Point


@cli.command()
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
def user_create(
    context: object,
    username: str,
    password: str,
    email: str,
    first_name: str,
    last_name: str,
):
    try:
        # Setup the pbench server config and db access
        config_setup(context, "pbench-user-create")

        user = User(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
        user.add()
        click.echo(f"User {username} registered")
        rv = 0
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)


# User delete CLI
@cli.command()
@common_options
@click.argument("username")
@pass_cli_context
def user_delete(context: object, username: str) -> None:
    context.username = username

    try:
        # Setup the pbench server config and db access
        config_setup(context, "pbench-user-delete")

        # Delete the the user with specified username
        User.delete(username=context.username)

        click.echo(f"User {context.username} deleted")
        rv = 0
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)


# Users list CLI
@cli.command()
@common_options
@pass_cli_context
def user_list(context: object) -> None:
    try:
        # Setup the pbench server config and db access
        config_setup(context, "pbench-users-list")

        ROW_FORMAT = "{10} {10} {%Y-%m-%d} {}"
        click.echo(
            ROW_FORMAT.format("First Name", "Last Name", "Registered On", "Email")
        )

        # Query all the users
        users = Database.db_session.query(User).all()
        for user in users:
            click.echo(
                ROW_FORMAT.format(
                    user.first_name, user.last_name, user.registered_on, user.email
                )
            )

        rv = 0
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)


# User update CLI
@cli.command()
@common_options
@click.argument("user-to-update")
@click.option(
    "--username", required=False, help="Specify the new username",
)
@click.option(
    "--email", required=False, help="Specify the new email",
)
@click.option(
    "--first-name", required=False, help="Specify the new first name",
)
@click.option(
    "--last-name", required=False, help="Specify the new last name",
)
@click.option(
    "--role", required=False, help="Specify the new role",
)
@pass_cli_context
def user_update(
    context: object,
    user_to_update: str,
    username: str,
    first_name: str,
    last_name: str,
    email: str,
    role: str,
) -> None:
    try:
        # Setup the pbench server config and db access
        config_setup(context, "pbench-user-update")

        # Query the user
        user = User.query(username=user_to_update)

        if user is None:
            click.echo(f"No such a user {user_to_update} to update")
            rv = 1
        else:
            dict_to_update = {}
            if username:
                dict_to_update["username"] = username

            if first_name:
                dict_to_update["first_name"] = first_name

            if last_name:
                dict_to_update["last_name"] = last_name

            if email:
                dict_to_update["email"] = email

            if role:
                dict_to_update["role"] = role

            # Update the user
            user.update(dict_to_update)

            click.echo(f"User {user_to_update} updated")
            rv = 0
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)


if __name__ == "__main__":
    cli(obj={})
