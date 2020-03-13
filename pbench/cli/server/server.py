import pkg_resources

from pbench.cli import base


class PbenchServerCli(base.PbenchCli):
    SCRIPT_NAME = "pbench-server-config-activate.sh"

    def run(self):
        script = pkg_resources.resource_filename(
            "pbench.cli.server", "scripts/" + self.SCRIPT_NAME
        )
        args = "{0} {1}".format(script, self.subcommand_args.get("args"))
        exit_code, output = base.shell_execute(args)
