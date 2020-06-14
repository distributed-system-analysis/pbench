import click
import click_completion
import pbr.version

click_completion.init()


@click.group()
@click.version_option(version=pbr.version.VersionInfo("pbench"))
@click.pass_context
def main(ctxt):
    """
    A benchmarking and performance analysis framework.

    Enable autocomplete issue:

     eval "$(_PBENCH_COMPLETE=source molecule)"
    """
    pass
