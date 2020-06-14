import click


@click.group()
@click.option(
    "--debug/--no-debug", help="Enable or disable debug mode, Default is disabled"
)
@click.pass_context
def main(ctxt, debug):
    ctxt.obj = {}
    ctxt.obj["args"] = {}
    ctxt.obj["args"]["debug"] = debug
