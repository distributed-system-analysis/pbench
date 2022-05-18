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

from typing import Any, Callable, Optional, List
import json
import logging
import os
import select
import signal
import socket
import socketserver
import string
import sys
import time

from ptd_client_server.lib import source_hashes


DEFAULT_PORT = 4950
DEFAULT_IP_ADDR = "0.0.0.0"

PROTO_VERSION = "3"
MAGIC_CLIENT = f"mlcommons/power client v{PROTO_VERSION}"
MAGIC_SERVER = f"mlcommons/power server v{PROTO_VERSION}"


FETCH_FILES_LIST = [
    "power/ptd_logs.txt",
    "ranging/spl.txt",
    "power/server.json",
    "power/server.log",
    "run_1/spl.txt",
]


class Proto:
    # TODO: escape/unescape binary data?

    def __init__(self, conn: socket.socket) -> None:
        self._buf = b""
        self._x: Optional[socket.socket] = conn

    def _recv_buf(self, buflen: int) -> bytes:
        assert self._x is not None
        # Issue: https://bugs.python.org/issue41437
        #        SIGINT blocked by socket operations like recv on Windows
        # Workaround: Instead of blocking on socket.recv(), we run select() with
        #             an one second timeout in a loop.
        while True:
            ready = select.select([self._x], [], [], 1)
            if ready[0]:
                return self._x.recv(buflen)

    def recv(self) -> Optional[str]:
        if self._x is None:
            return None

        done = b"\n" in self._buf
        while not done:
            recvd = self._recv_buf(1024 * 16)
            if len(recvd) == 0:
                self._close()
                return None
            self._buf += recvd
            done = b"\n" in recvd

        idx = self._buf.index(b"\n")
        result = self._buf[:idx].rstrip(b"\r")
        self._buf = self._buf[idx + len(b"\n") :]
        return result.decode(errors="replace")

    def send(self, data: str) -> None:
        if self._x is None:
            return
        try:
            self._x.sendall(data.encode() + b"\r\n")
        except OSError:
            logging.exception("Got an exception while sending a message to socket")
            self._close()

    def command(self, data: str) -> Optional[str]:
        if self._x is None:
            return None
        self.send(data)
        return self.recv()

    def recv_file(self, filename: str) -> None:
        with open(filename + ".tmp", "wb") as f:
            try:
                while True:
                    line = self.recv()
                    if line is None:
                        raise Exception(
                            "Remote peer disconnected while sending a file {filename!r}"
                        )

                    chunk_len = int(line, 10)
                    if chunk_len < 0:
                        raise ValueError("Negative chunk length")

                    if chunk_len == 0:
                        break

                    data = self._recv_len(chunk_len)
                    if data is None:
                        raise Exception(
                            "Remote peer disconnected while sending a file {filename!r}"
                        )

                    f.write(data)
            except Exception:
                self._close()
                raise
        os.rename(filename + ".tmp", filename)
        logging.info(f"Received {filename!r}")

    def send_file(self, filename: str) -> None:
        with open(filename, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                self.send(str(len(chunk)))
                if len(chunk) == 0:
                    break
                if self._x is not None:
                    self._x.sendall(chunk)
                else:
                    break

    def _recv_len(self, length: int) -> Optional[bytes]:
        if self._x is None:
            return None
        result = b""
        while length > 0:
            if len(self._buf) > 0:
                len2 = min(length, len(self._buf))
                result += self._buf[:len2]
                self._buf = self._buf[len2:]
                length -= len2
            else:
                recvd = self._recv_buf(min(1024 * 16, length))
                if len(recvd) == 0:
                    self._close()
                    return None
                result += recvd
                length -= len(recvd)
        return result

    def _close(self) -> None:
        if self._x is not None:
            try:
                self._x.close()
            except OSError:
                logging.exception("Got an exception while closing a socket")
            finally:
                self._x = None

    def enable_keepalive(self) -> None:
        after_idle_sec = 2
        interval_sec = 2
        max_fails = 10  # Not configurable on Windows, hardcoded to 10.
        # The connection considered timed out after
        # `after_idle_sec + (interval_sec * max_fails)` seconds of idle.

        if self._x is None:
            return
        if sys.platform == "win32":
            self._x.ioctl(
                socket.SIO_KEEPALIVE_VALS,
                (1, after_idle_sec * 1000, interval_sec * 1000),
            )
        elif sys.platform == "linux":
            self._x.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self._x.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, after_idle_sec)
            self._x.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval_sec)
            self._x.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, max_fails)
        elif sys.platform == "darwin":
            TCP_KEEPALIVE = 0x10
            self._x.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self._x.setsockopt(socket.IPPROTO_TCP, TCP_KEEPALIVE, interval_sec)
        else:
            logging.warning(
                "Keepalive not implemented for this platform ({sys.platform!r})"
            )


class SignalHandler:
    # See also:
    #   https://vorpus.org/blog/control-c-handling-in-python-and-trio/
    #   https://bugs.python.org/issue42340

    def __init__(self) -> None:
        self.stopped = False
        self.force_stopped = False
        self.on_stop: Callable[[], None] = lambda: sys.exit()
        self._enable_exception = False

    def init(self) -> None:
        signal.signal(signal.SIGINT, self._handle)

    def _handle(self, signum: int, frame: Any) -> None:
        if not self.stopped:
            logging.info("Performing graceful shutdown...")
            logging.info("Send SIGTERM (CTRL+C) again to abort")
            self.stopped = True
            self.on_stop()
            if self._enable_exception:
                raise KeyboardInterrupt
        else:
            logging.fatal(
                "Got SIGTERM signal again, aborting graceful shutdown and exiting..."
            )
            self.force_stopped = True
            exit(1)

    def check(self) -> None:
        if self.stopped:
            raise KeyboardInterrupt

    def __enter__(self) -> "SignalHandler":
        """Enable KeyboardInterrupt temporarely."""
        self._enable_exception = True
        if self.stopped:
            raise KeyboardInterrupt
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self._enable_exception = False
        pass


sig = SignalHandler()


def run_server(
    host: str,
    port: int,
    handle: Callable[[Proto], None],
) -> None:
    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            logging.info(f"Connected {self.client_address}")
            p = Proto(self.request)
            try:
                handle(p)
            except Exception:
                logging.exception("Got an exception")
            logging.info("Done processing")

    class Server(socketserver.TCPServer):
        # There are two independent toggles for the server socket.
        # 1. Allow two or more servers to run on the same port simultaneously.
        #    We do not need this.
        # 2. Allow the server to bind to the same port shortly after
        #    the server restart (`TIME_WAIT` state). We need this.
        # The problem that on Windows, allow_reuse_address controls
        # the first toggle, and on Linux, it controls the second toggle.
        # See also: https://bugs.python.org/issue41135
        allow_reuse_address = True if sys.platform != "win32" else False

        # same as default poll_interval in server_forever()
        timeout = 0.5

    done = False

    def stop() -> None:
        nonlocal done
        done = True

    with Server((host, port), Handler) as server:
        logging.info(f"Ready to accept connections at {host}:{port}")
        sig.on_stop = stop
        while not done:
            server.handle_request()


def check_label(label: str) -> bool:
    valid_chars = "-_" + string.ascii_letters + string.digits
    return all((c in valid_chars for c in label))


class BufferHandler(logging.Handler):
    def __init__(self) -> None:
        logging.Handler.__init__(self)
        self._records: Optional[List[logging.LogRecord]] = None

    def start(self) -> None:
        self._records = []

    def stop(self, fname: Optional[str] = None) -> None:
        if fname is None:
            self._records = None
            return
        assert self._records is not None
        records, self._records = self._records, None
        with open(fname, "w", newline="\n") as f:
            for record in records:
                f.write("%s\n" % self.format(record))

    def emit(self, record: logging.LogRecord) -> None:
        if self._records is not None:
            self._records.append(record)


log_redirect = BufferHandler()


def init(name: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=f"{name} %(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(), log_redirect],
    )
    sig.init()


def mkdir_if_ne(path: str) -> None:
    """mkdir if not exists"""
    if not os.path.exists(path):
        try:
            logging.info(f"Creating output directory {path!r}")
            os.mkdir(path)
        except FileNotFoundError:
            logging.fatal(
                f"Could not create directory {path!r}. "
                "Make sure all intermediate directories exist."
            )
            exit(1)
        return

    test_write_permission(path)


def test_write_permission(path: str) -> None:
    tmp_file_path = os.path.join(path, f"{time.time_ns()}.tmp")

    try:
        with open(tmp_file_path, "w") as tmp:
            tmp.close()
        os.remove(tmp_file_path)
    except Exception:
        logging.exception("Got an exception while checking write permission")
        exit(1)


def human_bytes(num: int) -> str:
    num = float(num)
    unit_labels = ["B", "kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    last_label = unit_labels[-1]

    for unit in unit_labels:
        if num < 1000 - 0.05:
            break
        if unit != last_label:
            num /= 1000

    return f"{num:.1f} {unit}"


def log_sources() -> None:
    logging.info("Sources: " + json.dumps(source_hashes.get()))


def system_check() -> None:
    if sys.version_info < (3, 7):
        logging.fatal("Python 3.7 or newer is required")
        exit(1)
    if sys.platform.startswith("cygwin"):
        logging.fatal("Python installed through Cygwin is not supported")
        exit(1)
