import click


#
# Agent options
#
def pbench_upload_user(f):
    return click.option(
        "-u", "--user", "user", default="", help="Specify username for server upload"
    )(f)


def pbench_server_prefix(f):
    return click.option(
        "-p", "--prefix", default="", help="Specify a prefix for server upload"
    )(f)


def pbench_show_server(f):
    return click.option("-S", "--show-server", required=False, help="Show server",)(f)


#
# Default options
#
