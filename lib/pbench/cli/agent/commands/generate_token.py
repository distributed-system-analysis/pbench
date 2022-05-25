"""pbench-generate-token"""

from json import JSONDecodeError

import click
import requests

from pbench.agent.base import BaseCommand
from pbench.cli.agent import pass_cli_context
from pbench.cli.agent.options import common_options


class GenerateToken(BaseCommand):
    def __init__(self, context):
        super().__init__(context)

    def execute(self):
        """Generate a token used to access the pbench server RESTful API"""

        server = self.config.agent.parser.get("results", "server_rest_url")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        # TODO:  The server does not currently accept the 'token_duration' key,
        #  so it just gets ignored, for now.
        payload = {
            "username": self.context.username,
            "password": self.context.password,
            "token_duration": self.context.token_duration,
        }
        uri = f"{server}/login"
        try:
            response = requests.post(uri, headers=headers, json=payload)
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(f"Cannot connect to '{uri}'") from exc

        try:
            payload = response.json()
        except JSONDecodeError:
            payload = {"message": response.text}

        if response.ok and "auth_token" in payload:
            click.echo(payload["auth_token"])
            return 0

        click.echo(
            payload["message"] if "message" in payload else response.reason, err=True
        )
        return 1


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
    "--token-duration",
    type=int,
    required=False,
    default=3600,
    show_default=True,
    help="number of seconds",
)
@pass_cli_context
def main(context, username, password, token_duration):
    context.username = username
    context.password = password
    context.token_duration = token_duration

    try:
        rv = GenerateToken(context).execute()
    except Exception as exc:
        click.echo(exc, err=True)
        rv = 1

    click.get_current_context().exit(rv)
