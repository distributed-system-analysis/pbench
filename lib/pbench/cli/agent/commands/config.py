"""
pbench-agent-config-activate
pbench-agent-config-ssh-key
"""
import os
import pwd
import pathlib
import shutil
import sys

import click

from pbench.agent import PbenchAgentConfig
from pbench.agent.base import BaseCommand
from pbench.cli.agent import CliContext, pass_cli_context


class KeyConfig(BaseCommand):
    """Install ssh key in the right place"""

    def __init__(self, context):
        super().__init__(context)

    def execute(self):
        ssh_key = self.context.key

        try:
            shutil.copy(ssh_key, (self.pbench_install_dir / "id_rsa"))
        except Exception as ex:
            click.secho(ex)
            return 1
        finally:
            try:
                uid = pwd.getpwnam(self.user).pw_uid
                gid = pwd.getpwnam(self.group).pw_gid
            except KeyError:
                return 0
            else:
                if ssh_key.exists():
                    os.chown(ssh_key, uid, gid)
                    os.chmod(ssh_key, 0o600)

        return 1


def _config_option(f):
    """Option for agent configuration"""

    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.config = value
        return value

    return click.argument(
        "config", expose_value=False, type=click.Path(exists=True), callback=callback
    )(f)


def _key_option(f):
    """Option for key configuration"""

    def callback(ctx, param, value):
        clictx = ctx.ensure_object(CliContext)
        clictx.key = pathlib.Path(value)
        return value

    return click.argument(
        "key", expose_value=False, type=click.Path(exists=True), callback=callback
    )(f)


@click.command()
@_config_option
@pass_cli_context
def activate(ctxt):
    """Copy the pbench-agent configuration file in the right
    spot.
    """
    try:
        """We dont use the base class here becuase there
        isn't a configuration file yet
        """
        config = PbenchAgentConfig(str(ctxt.config))

        idir = pathlib.Path(config.pbench_install_dir) / "config"
        shutil.copy(ctxt.config, idir)
        return 0
    except Exception as ex:
        click.secho(ex)
        return 1


@click.command()
@_config_option
@_key_option
@pass_cli_context
def key(ctxt):
    """Install the ssh key in the right spot"""
    status = KeyConfig(ctxt).execute()
    sys.exit(status)
