import click

from pbench.agent.config import AGENT_DEBUG, lookup_agent_configuration
from pbench.agent.sysinfo import SYSINFO_OPTS_AVAILABLE

AGENT_CONFIG = lookup_agent_configuration()


#
# pbench-clear-tools
#
def clearGroup(f):
    return click.option(
        "-g",
        "--group",
        "group",
        default="default",
        help="the group from which tools should be removed"
        "(the default group is 'default')",
    )(f)


def clearName(f):
    return click.option(
        "-n",
        "--name",
        "name",
        help="a specific tool to be removed."
        "If no tool is specified, all tools in the group are removed",
    )(f)


#
# pbench-list-tools
#
def listName(f):
    return click.option(
        "-n", "--name", "name", help="List the perftool groups wich str is used"
    )(f)


def listGroup(f):
    return click.option(
        "-g", "--group", "group", help="List the tools used in this str"
    )(f)


#
# pbench-register-tool
#
def nameRegister(f):
    return click.option("-n", "--name",)(f)


def labelRegister(f):
    return click.option("-l", "--label", "--labels", "labels_args")(f)


def groupRegister(f):
    return click.option("-g", "--group", "group", default="default")(f)


def installRegister(f):
    return click.option("--no-install/--install", default=True)(f)


def testLabelregister(f):
    return click.option("--test-label/--no-test-label", default=False)(f)


#
# pbench-list-triggers
#
def listTrigger(f):
    return click.option("-g", "--group", help="list the triggers used by this group")(f)


#
# pbench-register-triggers
#
def registerTrigger(f):
    return click.option("-g", "--group", default="default")(f)


def startTrigger(f):
    return click.option("--start-trigger")(f)


def stopTrigger(f):
    return click.option("--stop-trigger")(f)


#
# pbench-collect-sysinfo
#
def sysinfoDir(f):
    return click.option(
        "-d",
        "--dir",
        "sysinfo_dir",
        help=f"a directory where the benchmark will store and process data",
        type=click.Path(exists=True),
        required=False,
    )(f)


def groupSysinfo(f):
    return click.option(
        "-g",
        "--group",
        default="default",
        help="a tool group used in a benchmark (the default group is 'default')",
    )(f)


def sysSysinfo(f):
    return click.option(
        "--sysinfo",
        help="comma seperated values of system infrmation to be collected"
        f'availablle: {" ".join(str(x) for x in SYSINFO_OPTS_AVAILABLE)}',
    )(f)


def checkSysinfo(f):
    return click.option(
        "--check/--no-check",
        help="checks if sysinfo is set to one of the accepted values",
        default=False,
    )(f)


def sysOptions(f):
    return click.option("--options/--no-options", default=False,)(f)


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
def pbench_agent_config(f):
    """Option for agent configuration"""
    return click.option(
        "-C",
        "--config",
        default=AGENT_CONFIG,
        help=(
            "Path to a pbench-agent config. If provided pbench will load "
            "this config file first. By default is looking for config in "
            "'_PBENCH_AGENT_CONFIG' envrionment variable."
        ),
    )(f)


def pbench_agent_debug(f):
    """Turn on/off debug"""
    return click.option(
        "--debug",
        default=AGENT_DEBUG,
        help="Enable or disable debug mode. Default is disabled",
    )(f)
