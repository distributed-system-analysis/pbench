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
import re
import socket
import sys
import time
from typing import Optional

import dateutil.parser
import requests


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
) -> requests.Response:
    md5 = get_md5(tarball)
    uploaded = datetime.datetime.fromtimestamp(
        tarball.stat().st_mtime, tz=datetime.timezone.utc
    )
    meta = [f"global.server.legacy.migrated:'{uploaded:%Y-%m-%dT%H:%M}'"]
    if "::" in tarball.parent.name:
        satellite, _ = tarball.parent.name.split("::", 1)
        meta.append(f"server.origin:{satellite}")
    if metadata:
        meta.extend(metadata)

    with tarball.open("rb") as f:
        return requests.put(
            f"{server}/api/v1/upload/{tarball.name}",
            headers={
                "Content-MD5": md5,
                "content-type": "application/octet-stream",
                "authorization": f"bearer {token}",
            },
            params={"metadata": meta, "access": "public"},
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

    # The standard metadata keys here are modeled on those provided by the
    # 0.69-11 passthrough server.
    metadata = [
        f"global.server.legacy.hostname:{host}",
        f"global.server.legacy.sha1:{sha1}",
        f"global.server.legacy.version:{version}",
    ]
    if parsed.metadata:
        metadata.extend(parsed.metadata)

    # Process date range filtering arguments
    since: Optional[datetime.datetime] = None
    before: Optional[datetime.datetime] = None

    since_ts: Optional[float] = None
    before_ts: Optional[float] = None

    if parsed.since:
        since = dateutil.parser.parse(parsed.since)
        since_ts = since.timestamp()

    if parsed.before:
        before = dateutil.parser.parse(parsed.before)
        before_ts = before.timestamp()

    if since and before:
        if before <= since:
            print(
                f"SINCE ({since}) must be earlier than BEFORE ({before})",
                file=sys.stderr,
            )
            return 1

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

    # If a checkpoint file is specified, and already exists, load the list of
    # files already uploaded.
    checkpoint: Optional[Path] = None
    processed: list[str] = []
    if parsed.checkpoint:
        checkpoint = parsed.checkpoint
        if checkpoint.exists():
            if parsed.verify:
                print(f"Processing checkpoint state from {checkpoint}...")
            processed = checkpoint.read_text().splitlines()
            if parsed.verify:
                print(
                    f"Finished processing checkpoint data: {len(processed)} checkpointed files"
                )

    # Using the specified filters and checkpoint data, determine the set of
    # tarballs we'll try to upload.
    if parsed.verify:
        print("Identifying target tarballs")
    skipped = 0
    early = 0
    late = 0
    timer = time.time()
    if parsed.tarball.is_dir():
        pool = parsed.tarball.glob("**/*.tar.xz")
        which = []
        for t in pool:
            if time.time() >= timer + 5.0:
                sel = len(which)
                print(
                    f"[{early + late + skipped + sel} examined, {sel} selected, {skipped} skipped]"
                )
                timer = time.time()
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
                    print(f"[checkpoint] skip {t}")
                continue
            which.append(t)
    elif parsed.tarball.is_file():
        which = [parsed.tarball]
    else:
        print(f"Path {parsed.tarball} isn't a directory or file", file=sys.stderr)
        return 1
    if parsed.verify:
        print(
            f"Identified {len(which)} target tarballs: skipped {skipped}, {early} too old, {late} too new"
        )

    # We'll append successful uploads to the checkpoint file.
    checkwriter: Optional[TextIOWrapper] = None
    if checkpoint:
        checkwriter = checkpoint.open(mode="a")

    # Now start the upload, checkpointing each file after a successful upload
    #
    # We maintain the checkpoint file for --preview to assist in testing: if
    # you want to test with --preview and then do a real upload, delete the
    # checkpoint file! Also, note that using --preview after a failure will
    # change the checkpoint file; if you want to do that, you should use a
    # copy of the checkpoint file.
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

                    # TODO: can we handle NGINX's ugly 500 "storage error"
                    # gracefully somehow?
                    if response.headers["content-type"] in (
                        "text/html",
                        "text/xml",
                        "application/xml",
                        "text/plain",
                    ):
                        message = re.sub(r"[\n\s]+", " ", response.text)
                    elif response.headers["content-type"] == "application/json":
                        try:
                            message = response.json()
                        except Exception:
                            message = response.text
                    else:
                        message = f"{response.headers['content-type']}({response.text})"
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
