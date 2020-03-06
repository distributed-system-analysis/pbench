import click

@click.group()
@click.pass_context
def main(context):
    context.obj = {}
    context.obj["args"] = {}
    context.obj["args"]["config"] = config
