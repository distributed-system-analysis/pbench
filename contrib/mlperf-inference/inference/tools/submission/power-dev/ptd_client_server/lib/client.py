# Copyright 2018 The MLPerf Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================


from ptd_client_server.lib import common
from ptd_client_server.lib import summary as summarylib
from ptd_client_server.lib import time_sync
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import argparse
import base64
import logging
import os
import re
import shutil
import socket
import subprocess
import time
import uuid

LOADGEN_LOG_FILE = "mlperf_log_detail.txt"
LOADGEN_OTHER_FILES = [
    "mlperf_log_summary.txt",
]


class CommandSender:
    def __init__(self, server: common.Proto, summary: summarylib.Summary) -> None:
        self._server = server
        self._summary = summary

    def __call__(self, command: str, check: bool = False) -> str:
        logging.info(f"Sending command to the server: {command!r}")
        time_command = time.time()
        response = self._server.command(command)
        time_response = time.time()
        if response is None:
            logging.fatal("The server is disconnected")
            exit(1)
        logging.info(f"Got response: {response!r}")
        if check and response != "OK":
            logging.fatal("Got an unexpecting response from the server")
            exit(1)
        self._summary.message((command, time_command), (response, time_response))
        return response

    def download(self, command: str, fname: str) -> None:
        logging.info(f"Fetching file {fname!r}")
        self._server.send(command)
        self._server.recv_file(fname)


def check_paths(loadgen_logs: str, output: str, force: bool) -> None:
    loadgen_logs_dir = os.path.abspath(loadgen_logs)
    output_dir = os.path.abspath(output)

    if loadgen_logs_dir == output_dir:
        logging.fatal(
            f"INDIR ({loadgen_logs!r}) and OUTDIR ({output!r}) should not be the same directory"
        )
        exit(1)

    if loadgen_logs_dir == os.path.commonpath([loadgen_logs_dir, output_dir]):
        logging.fatal(
            f"OUTDIR ({output!r}) should not be the INDIR subdirectory ({loadgen_logs!r})"
        )
        exit(1)

    if os.path.exists(loadgen_logs) and force:
        logging.warning(f"Removing loadgen logs directory {loadgen_logs!r}")
        shutil.rmtree(loadgen_logs)


def command_get_file(server: common.Proto, command: str, save_name: str) -> None:
    logging.info(f"Sending command to the server: {command!r}")
    log = server.command(command)
    if log is None or not log.startswith("base64 "):
        logging.fatal("Could not get file from the server")
        exit(1)
    with open(save_name, "wb") as f:
        f.write(base64.b64decode(log[len("base64 ") :]))
    logging.info(f"Saving response to {save_name!r}")


def get_time_from_line(
    line: str, data_regexp: str, file: str, timezone_offset: int
) -> Optional[float]:
    # TODO: deduplicate with check.py?
    log_time_str = re.search(data_regexp, line)
    if log_time_str and log_time_str.group(0):
        log_datetime = datetime.strptime(log_time_str.group(0), "%m-%d-%Y %H:%M:%S.%f")
        return log_datetime.replace(tzinfo=timezone.utc).timestamp() + timezone_offset
    return None


def find_loadgen_logs(
    path: str, time_load_start: float, time_load_end: float
) -> Optional[str]:
    abs_path = path if os.path.isabs(path) else os.path.abspath(path)
    loadgen_logs_candidates = list(Path(abs_path).rglob(LOADGEN_LOG_FILE))
    for file in loadgen_logs_candidates:
        power_begin = None
        power_end = None
        with open(file) as f:
            for line in f:
                if re.search("power_begin", line.lower()):
                    power_begin = get_time_from_line(
                        line,
                        r"(\d*-\d*-\d* \d*:\d*:\d*\.\d*)",
                        str(file),
                        0,
                    )
                elif re.search("power_end", line.lower()):
                    power_end = get_time_from_line(
                        line,
                        r"(\d*-\d*-\d* \d*:\d*:\d*\.\d*)",
                        str(file),
                        0,
                    )
                if power_begin and power_end:
                    break
        if (
            power_begin
            and power_end
            and power_begin > time_load_start
            and power_end < time_load_end
        ):
            logs_dir = os.path.dirname(file)
            for other_file in LOADGEN_OTHER_FILES:
                if other_file not in os.listdir(logs_dir):
                    logging.error(f"There is no {other_file} in {logs_dir}")
            return logs_dir

    return None


def main() -> None:
    common.init("client")

    common.system_check()

    parser = argparse.ArgumentParser(
        description="PTD client",
        formatter_class=lambda prog: argparse.RawDescriptionHelpFormatter(
            prog, max_help_position=35
        ),
    )

    optional = parser._action_groups.pop()
    required = parser.add_argument_group("required arguments")

    # fmt: off
    required.add_argument(
        "-a", "--addr", metavar="ADDR", type=str, required=True,
        help="server address")
    required.add_argument(
        "-w", "--run-workload", metavar="CMD", type=str, required=True,
        help="a shell command to run under power measurement")
    required.add_argument(
        "-L", "--loadgen-logs", metavar="INDIR", type=str, required=True,
        help="collect loadgen logs from INDIR")
    required.add_argument(
        "-o", "--output", metavar="OUTDIR", type=str, required=True,
        help="put logs into OUTDIR (copied from INDIR)")
    required.add_argument(
        "-n", "--ntp", metavar="ADDR", type=str, required=True,
        help="NTP server address")

    parser.add_argument(
        "-T", "--no-timestamp-path", action="store_true",
        help="don't add timestamp to the logs path"
    )
    parser.add_argument(
        "-t", "--timestamp-path", action="store_false", dest="no_timestamp_path",
        help="add timestamp to the logs path [default]"
    )
    parser.add_argument(
        "-p", "--port", metavar="PORT", type=int, default=4950,
        help="server port, defaults to 4950")
    parser.add_argument(
        "-l", "--label", metavar="LABEL", type=str, default="",
        help="a label to include into the resulting directory name")
    parser.add_argument(
        "-f", "--force", action="store_true",
        help="force remove loadgen logs directory (INDIR)")
    parser.add_argument(
        "-S", "--stop-server", action="store_true",
        help="stop the server after processing this client")
    # fmt: on
    common.log_redirect.start()

    parser._action_groups.append(optional)
    args = parser.parse_args()

    if not common.check_label(args.label):
        parser.error(
            "invalid --label value: {args.label!r}. Should be alphanumeric or -_."
        )

    if args.port is None:
        args.port = common.DEFAULT_PORT
        logging.warning(f"Assuming default port (--port {common.DEFAULT_PORT}")

    check_paths(args.loadgen_logs, args.output, args.force)

    common.mkdir_if_ne(args.output)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((args.addr, args.port))
    except OSError as e:
        s.close()
        logging.fatal(f"Could not connect to the server {args.addr}:{args.port} {e}")
        exit(1)

    serv = common.Proto(s)
    serv.enable_keepalive()

    summary = summarylib.Summary()

    command = CommandSender(serv, summary)

    # TODO: timeout and max msg size for recv
    magic = command(common.MAGIC_CLIENT)
    if magic != common.MAGIC_SERVER:
        logging.error(
            f"Handshake failed, expected {common.MAGIC_SERVER!r}, got {magic!r}"
        )
        exit(1)
    del magic

    if args.stop_server:
        # Enable the "stop" flag on the server so it will stop after the client
        # disconnects.  We are sending this early to make sure the server
        # eventually will stop even if the client crashes unexpectedly.
        command("stop", check=True)

    def sync_check() -> None:
        if not time_sync.sync(
            args.ntp,
            lambda: float(command("time")),
            lambda: command("set_ntp"),
        ):
            exit()

    sync_check()

    summary.client_uuid = uuid.uuid4()
    try:
        session = command(f"new,{args.label},{summary.client_uuid}")
        if session is None or not session.startswith("OK "):
            logging.fatal("Could not start new session")
            exit(1)
        session, server_uuid = session[len("OK ") :].split(",")
    except Exception:
        exit(1)
    summary.server_uuid = uuid.UUID(server_uuid)
    summary.session_name = session
    logging.info(f"Session id is {session!r}")

    common.log_sources()
    if args.no_timestamp_path:
        out_dir = args.output
        power_dir = os.path.join(args.output, "power")
    else:
        out_dir = os.path.join(args.output, session)
        os.mkdir(out_dir)
        power_dir = os.path.join(args.output, session, "power")
    os.mkdir(power_dir)

    for mode in ["ranging", "testing"]:
        logging.info(f"Running workload in {mode} mode")
        out = os.path.join(out_dir, "run_1" if mode == "testing" else mode)

        sync_check()

        summary.phase(mode, 0)
        command(f"session,{session},start,{mode}", check=True)

        summary.phase(mode, 1)
        logging.info(f"Running the workload {args.run_workload!r}")
        time_load_start = time.time()
        subprocess.run(args.run_workload, shell=True, check=True)
        time_load_end = time.time()
        summary.phase(mode, 2)

        command(f"session,{session},stop,{mode}", check=True)
        summary.phase(mode, 3)

        loadgen_logs = find_loadgen_logs(
            args.loadgen_logs, time_load_start, time_load_end
        )

        if not loadgen_logs:
            logging.fatal(
                f"Expected {args.loadgen_logs!r} to be a directory containing loadgen logs, but it is not"
            )
            logging.fatal(
                "Please make sure that the provided workload command writes its "
                "output into the directory specified by the --loadgen-logs/-L argument"
            )
            exit(1)

        logging.info(f"Copying loadgen logs from {loadgen_logs!r} to {out!r}")
        os.mkdir(out)
        for file in [LOADGEN_LOG_FILE] + LOADGEN_OTHER_FILES:
            shutil.copy(os.path.join(loadgen_logs, file), out)

    logging.info("Done runs")

    client_log_path = os.path.join(power_dir, "client.log")
    common.log_redirect.stop(client_log_path)

    summary.hash_results(out_dir)

    client_json_path = os.path.join(power_dir, "client.json")
    summary.save(client_json_path)

    command(f"session,{session},done", check=True)

    for fname in common.FETCH_FILES_LIST:
        command.download(f"download,{session},{fname}", os.path.join(out_dir, fname))

    command(f"cleanup,{session}", check=True)

    logging.info("Successful exit")
