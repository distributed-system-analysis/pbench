import click
import click_completion
import pbr.version

click_completion.init()


@click.group()
@click.option(
    "--debug/--no-debug", help="Enable or disable debug mode, Default is disabled"
)
@click.version_option(version=pbr.version.VersionInfo("pbench"))
@click.pass_context
def main(ctxt, debug):
    """
    A benchmarking and performance analysis framework.

    Enable autocomplete issue:

     eval "$(_PBENCH_COMPLETE=source molecule)"
    """
    ctxt.obj = {}
    ctxt.obj["args"] = {}
    ctxt.obj["args"]["debug"] = debug
