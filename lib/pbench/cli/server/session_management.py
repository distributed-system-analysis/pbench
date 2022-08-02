import logging

import click

from pbench import BadConfig
from pbench.cli.server import pass_cli_context
from pbench.cli.server.options import common_options
from pbench.server import PbenchServerConfig
from pbench.server.auth.exceptions import KeycloakConnectionError
from pbench.server.auth.keycloak_admin import Admin


# Keycloak user session cli
@click.group("user_sessions")
@click.version_option()
@pass_cli_context
@common_options
def user_command_cli(context):
    # Entry point
    pass


@user_command_cli.command()
@pass_cli_context
@click.option(
    "--user_id",
    required=False,
    help="Keycloak user id",
)
@click.option(
    "--username",
    required=False,
    help="Keycloak username",
)
@click.option(
    "--realm",
    required=False,
    help="Keycloak realm name",
)
@common_options
def get_user_sessions(context, user_id, username, realm):
    try:
        logger = logging.getLogger(__name__)
        config = PbenchServerConfig(context.config)
        keycloak_admin = Admin(
            server_url=config.get("keycloak", "server_url"),
            realm_name="Master",
            client_id="admin-cli",
            logger=logger,
        )
        if user_id:
            all_user_sessions = keycloak_admin.get_all_user_sessions(
                user_id=user_id, realm=realm
            )
        elif username:
            user_id = keycloak_admin.get_user_id(username=username)
            all_user_sessions = keycloak_admin.get_all_user_sessions(
                user_id=user_id, realm=realm
            )
        else:
            click.echo("Either username or user_id is required", err=True)
            click.get_current_context().exit(1)
        click.echo(all_user_sessions)
        rv = 0
    except BadConfig as exc:
        rv = 2
        click.echo(exc, err=True)
    except KeycloakConnectionError as exc:
        rv = 3
        click.echo(exc, err=True)
    except Exception as exc:
        rv = 1
        click.echo(exc, err=True)

    click.get_current_context().exit(rv)


@user_command_cli.command()
@pass_cli_context
@click.option(
    "--client_id",
    required=False,
    help="Keycloak client id",
)
@click.option(
    "--client_name",
    required=False,
    help="Keycloak client name",
)
@click.option(
    "--realm",
    required=False,
    help="Keycloak realm name",
)
@common_options
def get_client_sessions(context, client_id, client_name, realm):
    try:
        logger = logging.getLogger(__name__)
        config = PbenchServerConfig(context.config)
        keycloak_admin = Admin(
            server_url=config.get("keycloak", "server_url"),
            realm_name="Master",
            client_id="admin-cli",
            logger=logger,
        )
        if client_id:
            all_client_sessions = keycloak_admin.get_client_all_sessions(
                client_id=client_id, realm=realm
            )
        elif client_name:
            client_id = keycloak_admin.get_client(client_name=client_name)[0]["id"]
            all_client_sessions = keycloak_admin.get_client_all_sessions(
                client_id=client_id, realm=realm
            )
        else:
            click.echo("Either client name or client_id is required", err=True)
            click.get_current_context().exit(1)
        click.echo(all_client_sessions)
        rv = 0
    except BadConfig as exc:
        rv = 2
        click.echo(exc, err=True)
    except KeycloakConnectionError as exc:
        rv = 3
        click.echo(exc, err=True)
    except Exception as exc:
        rv = 1
        click.echo(exc, err=True)

    click.get_current_context().exit(rv)
