import click
import pbr.version


@click.group()
@click.option(
    "--debug/--no-debug", help="Enable or disable debug mode, Default is disabled"
)
@click.version_option(version=pbr.version.VersionInfo("pbench"))
@click.pass_context
def main(ctxt, debug):
    ctxt.obj = {}
    ctxt.obj["args"] = {}
    ctxt.obj["args"]["debug"] = debug
