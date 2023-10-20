#!/usr/bin/env python3.9

"""Upload results tarballs to a Pbench Server

This utility supports bulk migration of results tarballs to a Pbench Server.

It's a standalone utility (with no dependency on any Pbench packages) that can
be used to send a specific tarball or a potentially large set of tarballs to a
server. It supports filtering by file modification date, and checkpointing to
allow restarting in case of a failure. It can be run in a "preview" mode to
identify the selected tarballs without uploading.

`pbench-upload-results.py https://<server> /srv/pbench/backup` will upload all
result tarballs nested under the directory `/srv/pbench/backup`. You can use
the `--since` and `--before` timestamp selectors to include only results files
modified "since" (>=) and/or "before" (<) the specified datetimes. Specify a
checkpoint file with `--checkpoint <file>` to record all results successfully
uploaded; after unexpected termination (e.g., crash or ^C), rerunning the same
command will skip the already uploaded files.

Uploaded files are marked with metadata consistent with the behavior of the
0.69-11 passthrough server. If the script is run on a Pbench server, metadata
will record the version string and SHA1 of the Pbench installation. We also
record the hostname, and a marker that it was "migrated" by this utility.
"""
from argparse import ArgumentParser
import datetime
from http import HTTPStatus
from io import TextIOWrapper
from pathlib import Path
import socket
import sys
from typing import Optional

from dateutil import parser as date_parser
import requests
from requests import Response


def get_md5(tarball: Path) -> str:
    """Read the tarball MD5 from the tarball's companion file

    Args:
        tarball: Path to a tarball file with a {name}.md5 companion

    Returns:
        The tarball's MD5 value
    """
    md5_file = Path(f"{str(tarball)}.md5")
    return md5_file.read_text().split()[0]


def upload(
    server: str, token: str, tarball: Path, metadata: Optional[list[str]] = None
) -> Response:
    query_parameters = {}

    md5 = get_md5(tarball)
    query_parameters["access"] = "public"
    dataset = tarball.name
    satellite, _ = tarball.parent.name.split("::")
    meta = [
        f"global.server.legacy.migrated:{datetime.datetime.now(tz=datetime.timezone.utc):%Y-%m-%dT%H:%M}"
    ]
    if satellite:
        meta.append(f"server.origin:{satellite}")
    if metadata:
        meta.extend(metadata)
    query_parameters["metadata"] = meta
    headers = {
        "Content-MD5": md5,
        "content-type": "application/octet-stream",
        "authorization": f"bearer {token}",
    }

    with tarball.open("rb") as f:
        return requests.put(
            f"{server}/api/v1/upload/{dataset}",
            headers=headers,
            params=query_parameters,
            data=f,
        )


def main() -> int:
    prog = Path(sys.argv[0])
    parser = ArgumentParser(prog=prog.name, description="Upload tarballs")
    parser.add_argument("server", help="Specify the Pbench Server address")
    parser.add_argument(
        "tarball", type=Path, help="Specify a tarball or directory path"
    )
    parser.add_argument("-b", "--before", help="Select tarballs older than this")
    parser.add_argument(
        "-c",
        "--checkpoint",
        type=Path,
        dest="checkpoint",
        help="Checkpoint file for restart",
    )
    parser.add_argument(
        "-m",
        "--metadata",
        action="append",
        dest="metadata",
        help="Set metadata on dataset upload",
    )
    parser.add_argument(
        "-p",
        "--preview",
        action="store_true",
        help="Report actions but make no changes",
    )
    parser.add_argument(
        "-s", "--since", action="store", help="Select tarballs no older than this"
    )
    parser.add_argument(
        "-t", "--token", action="store", dest="token", help="Pbench Server API token"
    )
    parser.add_argument(
        "--verify", "-v", dest="verify", action="store_true", help="Show progress"
    )
    parsed = parser.parse_args()

    # Get basic configuration
    host = socket.gethostname()
    v = Path("/opt/pbench-server/VERSION")
    s = Path("/opt/pbench-server/SHA1")
    version = v.read_text().strip() if v.exists() else "unknown"
    sha1 = s.read_text().strip() if s.exists() else "unknown"
    metadata = [
        f"global.server.legacy.hostname:{host}",
        f"global.server.legacy.sha1:{sha1}",
        f"global.server.legacy.version:{version}",
    ]
    if parsed.metadata:
        metadata.extend(parsed.metadata)

    since: Optional[datetime.datetime] = None
    before: Optional[datetime.datetime] = None

    since_ts: Optional[float] = None
    before_ts: Optional[float] = None

    if parsed.since:
        since = date_parser.parse(parsed.since)
        since_ts = since.timestamp()

    if parsed.before:
        before = date_parser.parse(parsed.before)
        before_ts = before.timestamp()

    if since and before:
        when = f" (from {since:%Y-%m-%d %H:%M} to {before:%Y-%m-%d %H:%M})"
    elif since:
        when = f" (since {since:%Y-%m-%d %H:%M})"
    elif before:
        when = f" (before {before:%Y-%m-%d %H:%M})"
    else:
        when = ""

    if parsed.tarball.is_dir():
        what = f"DIRECTORY {parsed.tarball}"
    else:
        what = f"TARBALL {parsed.tarball}"

    print(f"{what}{when} -> SERVER {parsed.server}")

    checkpoint: Optional[Path] = None
    processed: list[str] = []
    if parsed.checkpoint:
        checkpoint = parsed.checkpoint
        if parsed.verify:
            print(f"Processing checkpoint state from {checkpoint}...")
        if checkpoint.exists():
            processed = checkpoint.read_text().splitlines()
            if parsed.verify:
                print(f"[CPT] done {len(processed)}")
        if parsed.verify:
            print(
                f"Finished processing checkpoint data: {len(processed)} checkpointed files"
            )

    if parsed.verify:
        print("Identifying target tarballs")
    skipped = 0
    early = 0
    late = 0
    if parsed.tarball.is_dir():
        pool = parsed.tarball.glob("**/*.tar.xz")
        which = []
        for t in pool:
            if not t.is_file():
                continue
            date = t.stat().st_mtime
            if since_ts and date < since_ts:
                early += 1
                continue
            if before_ts and date >= before_ts:
                late += 1
                continue
            if str(t) in processed:
                skipped += 1
                if parsed.verify:
                    print(f"[CPT] skip {t}")
                continue
            which.append(t)
    elif parsed.tarball.is_file():
        which = [parsed.tarball]
    else:
        print(f"Path {parsed.tarball} doesn't exist", file=sys.stderr)
        return 1
    if parsed.verify:
        print(
            f"Identified {len(which)} target tarballs: skipped {skipped}, {early} too old, {late} too new"
        )

    checkwriter: Optional[TextIOWrapper] = None
    if checkpoint:
        checkwriter = checkpoint.open(mode="a")

    if parsed.verify:
        print("Uploading target files...")
    success = 0
    failure = 0
    failures = set()
    duplicate = 0
    for t in which:
        try:
            if parsed.preview:
                print(f"UPLOAD {t}")
                success += 1
                if checkwriter:
                    print(t, file=checkwriter, flush=True)
            else:
                response = upload(parsed.server, parsed.token, t, metadata=metadata)
                if response.ok:
                    if response.status_code == HTTPStatus.OK:
                        duplicate += 1
                    else:
                        success += 1
                    if parsed.verify:
                        print(f"UPLOAD {t}: {response.status_code}")
                    if checkwriter:
                        print(t, file=checkwriter, flush=True)
                else:
                    failure += 1
                    failures.add(response.status_code)
                    try:
                        message = response.json()
                    except Exception:
                        message = response.text
                    print(
                        f"Upload of {t} failed: {response.status_code} ({message})",
                        file=sys.stderr,
                    )
        except Exception as e:
            failure += 1
            print(f"Failed uploading {t}: {str(e)!r}", file=sys.stderr)

    if checkwriter:
        checkwriter.close()

    print(
        f"Uploaded {success} successfully; {duplicate} duplicates, {failure} failures: {failures}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
