# -*- mode: python -*-

"""Tool Meister "Kill"

Module responsible for hunting down and stopping all Tool Meisters, the Tool
Data Sink, and the Redis server orchestrated by pbench-tool-meister-start.

This is a "big hammer" approach that is offered to users when they find the
distributed system state of the Pbench Agent not working correctly.

The algorithm is fairly straight-forward:

  For each pbench run directory in ${pbench_run}
  1. If the run was NOT orchestrated by pbench-tool-meister-start, ignore
  2. Find the recorded pids for the Redis Server, Tool Data Sink, and local
     Tool Meister in their respective pid files, and stop those processes
     from running
  3. Determine all the remote hosts used for that run
  4. For each remote host:
     a. `ssh` to that remote host
     b. Stop the Tool Meister running on that host

The pbench-tool-meister-start generates a UUID for the entire session and
inserts that value into each command line of spawned remote Tool Meister
processes. Any Tool Meister process with that UUID in its command line string
will be stopped via `kill -KILL`, along with all of its child processes.
"""

from collections import defaultdict
import pathlib
import shlex
from typing import Callable, Dict, Iterable, List, Tuple

import click
import psutil

from pbench.agent.base import BaseCommand
from pbench.agent.tool_group import gen_tool_groups
from pbench.agent.utils import LocalRemoteHost, TemplateSsh
from pbench.cli.agent import CliContext, pass_cli_context
from pbench.cli.agent.options import common_options


def kill_family(proc: psutil.Process):
    """Kill a parent process and all its children."""
    try:
        # Get the list of children of the parent before killing it.
        children = list(proc.children(recursive=True))
    except psutil.NoSuchProcess:
        return
    try:
        proc.kill()
    except psutil.NoSuchProcess:
        pass
    for child in children:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass


class PidSource:
    """For a given PID file name keep track of discovered Process-es and UUIDs as
    Tool Meister directories are `load()`ed.  The `killem()` method is invoked
    by the caller at its discretion.

    The `killem()` method clears out all accumlated data.
    """

    def __init__(self, file_name: str, display_name: str):
        self.file_name = file_name
        self.display_name = display_name
        self.procs_by_uuid: Dict[str, psutil.Process] = {}
        self.uuid_to_tmdir: Dict[str, pathlib.Path] = {}

    def load(self, tm_dir: pathlib.Path, uuid: str) -> bool:
        """Load a PID from the given directory associated with the given UUID.

        Records the loaded PID if it has a live process associated with it and
        returns True, otherwise returns False.
        """
        try:
            pid = (tm_dir / self.file_name).read_text()
        except FileNotFoundError:
            return False
        try:
            self.procs_by_uuid[uuid] = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return False
        self.uuid_to_tmdir[uuid] = tm_dir
        return True

    def killem(self, echo: Callable[[str], None]) -> None:
        """Kill all PIDs found, and their children."""
        if not self.procs_by_uuid:
            return
        echo(f"Killing {self.display_name} PIDs ...")
        # Clear out the stored data ahead of the killings.
        procs_by_uuid, self.procs_by_uuid = self.procs_by_uuid, {}
        uuid_to_tmdir, self.uuid_to_tmdir = self.uuid_to_tmdir, {}
        for uuid, proc in procs_by_uuid.items():
            pid = proc.pid
            echo(f"\tKilling {pid} (from {uuid_to_tmdir[uuid]})")
            try:
                kill_family(proc)
            except Exception as exc:
                echo(f"\t\terror killing {pid}: {exc}", err=True)


def gen_run_directories(pbench_run: pathlib.Path) -> Iterable[Tuple[pathlib.Path, str]]:
    """Generate the list of run directories available under ${pbench_run},
    yielding a Path object for that directory, along with its recorded
    UUID.

    Yields a tuple of the run directory Path object and associated UUID.
    """
    for entry in pbench_run.iterdir():
        if not entry.is_dir():
            continue
        tm_dir = entry / "tm"
        try:
            uuid = (tm_dir / ".uuid").read_text()
        except FileNotFoundError:
            # This is either not a pbench run directory, or the Tool Meister
            # sub-system was not orchestrated by pbench-tool-meister-start
            # for this run.
            continue
        yield tm_dir, uuid


def gen_host_names(tm_dir: pathlib.Path) -> Iterable[str]:
    """Read the registered tool data saved for this run and return the list
    of remote hosts.
    """
    run_dir = tm_dir.parent
    tool_groups = list(gen_tool_groups(run_dir))
    if not tool_groups:
        return

    lrh = LocalRemoteHost()

    for tg in tool_groups:
        for host_name in tg.hostnames.keys():
            if lrh.is_local(host_name):
                continue
            yield host_name


class KillTools(BaseCommand):
    """Find and stop all orchestrated Tool Meister instances."""

    def execute(self, uuids: List[str]) -> int:
        """Execute the tools kill operation.

        If any UUIDs are passed as arguments, we only want to look for, and
        locally kill, processes having those UUIDs.

        Without command line arguments, kill all the local PIDs from all the
        discovered run directories.

        All the Redis server PIDs are killed first, then the Tool Data Sinks,
        and finally the local Tool Meisters.

        We then remotely kill (via `ssh`) all the Tool Meisters by invoking
        this same command on a remote host with the list of UUIDs found across
        all runs involving that host.
        """
        if uuids:
            # We have a list of UUIDs to kill, implying that we search locally
            # by UUID and only kill those PIDs found with the UUID in their
            # registered command line.
            for proc in psutil.process_iter():
                # Consider each command line element.
                for el in proc.cmdline():
                    for uuid in uuids:
                        if uuid in el:
                            pid = proc.pid
                            click.echo(f"\tKilling {pid} with UUID '{uuid}'")
                            try:
                                kill_family(proc)
                            except Exception as exc:
                                click.echo(f"\t\terror killing {pid}: {exc}", err=True)
            return 0

        # All three dictionaries for PID files that might be found, in the
        # order in which we'll kill their PIDs.
        all_pids = [
            PidSource("redis.pid", "redis server"),
            PidSource("pbench-tool-data-sink.pid", "tool data sink"),
            PidSource("tm.pid", "local tool meister"),
        ]
        local_pids = False
        remote_tms = defaultdict(list)
        for tm_dir, uuid in gen_run_directories(self.pbench_run):
            # If a run directory has any dangling components of the Tool
            # Meister sub-system active, that is PID files for any local
            # component, record those components.
            local_pids |= any([pidsrc.load(tm_dir, uuid) for pidsrc in all_pids])
            # Find all the remotes for this run that need to be tracked down.
            for host in gen_host_names(tm_dir.parent):
                remote_tms[host].append(uuid)

        if not local_pids and not remote_tms:
            # No local or remote pids found, nothing to do.
            return 0

        # Kill all the local PIDs (and their children).

        # We kill all the Redis Servers first in case killing them causes all
        # the other processes to just exit on their own.  Then we kill all the
        # Tool Data Sinks, and their children.  Then we kill all the (local)
        # Tool Meisters, and their children.
        for pidsrc in all_pids:
            pidsrc.killem(click.echo)

        # Kill all the remote Tool Meisters.

        cmd = "pbench-tools-kill {{uuids}}"
        template = TemplateSsh("ssh", shlex.split(self.ssh_opts), cmd)

        # First fire off a number of background ssh processes, one per remote
        # host.
        remotes = []
        for host, uuids in remote_tms.items():
            click.echo(f"Killing all Tool Meister processes on remote host {host}...")
            template.start(host, uuids=" ".join(uuids))
            remotes.append(host)

        # Wait for them all to complete, oldest to youngest.
        for host in remotes:
            template.wait(host)

        return 0


@click.command(
    help="Ensure all instances of running tools are stopped locally or remotely"
)
@common_options
@click.argument("uuids", nargs=-1)
@pass_cli_context
def main(ctxt: CliContext, uuids: List[str]):
    status = KillTools(ctxt).execute(uuids)
    click.get_current_context().exit(status)
