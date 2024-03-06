from collections import defaultdict
import datetime
from typing import Iterator, Optional

import click

from pbench.cli import pass_cli_context
from pbench.cli.server import config_setup, Verify
from pbench.cli.server.options import common_options
from pbench.server import BadConfig, OperationCode
from pbench.server.database.database import Database
from pbench.server.database.models.audit import Audit, AuditStatus, AuditType

COLUMNS = (
    "id",
    "root_id",
    "name",
    "operation",
    "object_type",
    "object_id",
    "object_name",
    "user_id",
    "user_name",
    "status",
    "reason",
)

verifier: Optional[Verify] = None


def auditor(kwargs) -> Iterator[str]:
    """Report audit records matching patterns.

    Args:
        kwargs: the command options.

    Returns:
        A sequence of lines to be written
    """

    summary = kwargs.get("summary")
    open: dict[int, Audit] = {}
    query = (
        Database.db_session.query(Audit)
        .order_by(Audit.timestamp)
        .execution_options(stream_results=True)
    )
    filters = []
    for k in COLUMNS:
        if kwargs.get(k):
            filters.append(getattr(Audit, k) == kwargs.get(k))
    since = kwargs.get("since")
    until = kwargs.get("until")
    if since:
        filters.append(Audit.timestamp >= since)
    if until:
        filters.append(Audit.timestamp <= until)
    query = query.filter(*filters)
    if not summary:
        yield "Audit records:\n"
    rows = query.yield_per(2000)
    count = 0
    status = defaultdict(int)
    for audit in rows:
        duration = ""
        count += 1
        status[audit.status] += 1

        # If we're showing both start and termination events, we can compute
        # the duration of an operation; so save "open" BEGIN event timestamps
        # until we reach the matching termination (SUCCESS. FAILURE, WARNING).
        if audit.status is AuditStatus.BEGIN:
            open[audit.id] = audit
        else:
            if audit.root_id in open:
                delta: datetime.timedelta = (
                    audit.timestamp - open[audit.root_id].timestamp
                )
                d = float(delta.seconds) + (delta.microseconds / 1000000.0)
                duration = f" [{d:.3f} seconds]"
                del open[audit.root_id]
        if summary:
            if duration:
                yield (
                    f"[{audit.timestamp:%Y-%m-%d %H:%M:%S}] {audit.name} "
                    f"{audit.object_name} {audit.status.name} ({audit.user_name}){duration}\n"
                )
            continue
        yield f"  [{audit.timestamp}] : {audit.name} {audit.status.name}{duration}\n"
        yield f"    {audit.object_type.name} {audit.object_name} by user {audit.user_name}\n"
        if kwargs.get("ids"):
            yield (
                f"    ID {audit.id}, ROOT {audit.root_id}: OBJ "
                f"{audit.object_id}, UID {audit.user_id}\n"
            )
        if audit.attributes:
            yield f"      {audit.attributes}\n"
    yield ""
    yield f"Reported {count:,d} audit events:\n"
    for s, c in status.items():
        yield f"    {s.name:>10s} {c:>10,d}\n"
    if open:
        yield f"{len(open):,d} unterminated events:\n"
        for audit in open.values():
            yield (
                f"  [{audit.timestamp:%Y-%m-%d %H:%M:%S}] {audit.id:10d} "
                f"{audit.name} {audit.object_name} ({audit.user_name}) {audit.attributes}\n"
            )


@click.command(name="pbench-audit")
@pass_cli_context
@click.option(
    "--ids",
    default=False,
    is_flag=True,
    help="Show user and object IDs as well as names",
)
@click.option("--name", type=str, help="Select by audit event name")
@click.option(
    "--operation",
    type=click.Choice([o.name for o in OperationCode], case_sensitive=False),
    help="Select by audit operation name",
)
@click.option(
    "--object-type",
    type=click.Choice([t.name for t in AuditType], case_sensitive=False),
    help="Select by object type",
)
@click.option("--object-id", type=str, help="Select by object ID")
@click.option("--object-name", type=str, help="Select by object name")
@click.option("--page", default=False, is_flag=True, help="Paginate the output")
@click.option("--user-id", type=str, help="Select by user ID")
@click.option("--user-name", type=str, help="Select by username")
@click.option(
    "--status",
    type=click.Choice([s.name for s in AuditStatus], case_sensitive=False),
    help="Select by operation status",
)
@click.option(
    "--summary", default=False, is_flag=True, help="Show one-line summary of operations"
)
@click.option(
    "--since",
    type=click.DateTime(),
    help="Select entries on or after specified date/time",
)
@click.option(
    "--until",
    type=click.DateTime(),
    help="Select entries on or before specified date/time",
)
@click.option(
    "--verify", "-v", default=False, is_flag=True, help="Display intermediate messages"
)
@common_options
def audit(context: object, **kwargs):
    """Query and format the audit DB table

    The Audit table records a sequence of event representing all changes made
    to the data controlled by the Pbench Server. This tool supports queries to
    display audit events based on various search criteria including timestamp,
    user, object identification, and others.
    \f

    Args:
        context: click context
        kwargs: click options
    """
    global verifier
    verifier = Verify(kwargs.get("verify"))

    try:
        config_setup(context)
        if kwargs.get("page"):
            click.echo_via_pager(auditor(kwargs))
        else:
            for line in auditor(kwargs):
                click.echo(line, nl=False)
        rv = 0
    except Exception as exc:
        if verifier.verify:
            raise
        click.secho(exc, err=True, bg="red")
        rv = 2 if isinstance(exc, BadConfig) else 1

    click.get_current_context().exit(rv)
