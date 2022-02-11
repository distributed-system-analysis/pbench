import ifaddr
import ipaddress
import logging
import os
import signal
import socket
import subprocess
import sys
import time

from datetime import datetime

from pbench.agent.constants import (
    def_redis_port,
    sysinfo_opts_available,
    sysinfo_opts_convenience,
    sysinfo_opts_default,
)
from pbench.common.utils import validate_hostname


class BaseReturnCode:
    """BaseReturnCode - base class of common methods for symbolic return codes
    for main programs.
    """

    # Common success code is zero.
    SUCCESS = 0

    # Common kill sub-codes
    KILL_SUCCESS = 0
    KILL_READEXC = 1
    KILL_BADPID = 2
    KILL_READERR = 3
    KILL_TERMEXC = 4
    KILL_KILLEXC = 5

    class Err(RuntimeError):
        """Err - exception definition to capture return code as an attribute.
        """

        def __init__(self, message: str, return_code: int):
            """Adds a return_code attribute to capture an integer representing
            the return code a caller can pass along.
            """
            super().__init__(message)
            self.return_code = return_code

    @staticmethod
    def kill_ret_code(kill_code: int, ret_val: int):
        """kill_ret_code - return an integer return code made up of the given
        kill code and a return value.

        A kill code of 0 and return value of 42 is returned as 42.
        A kill code of 5 and return value of 52 is returned as 542.
        """
        return (kill_code * 100) + ret_val


class BaseServer:
    """BaseServer - abstract base class for common code shared between the
    ToolDataSink and RedisServer classes.
    """

    def_port = None
    bad_port_ret_code = None
    bad_host_ret_code = None
    name = None

    class Err(BaseReturnCode.Err):
        """BaseServer.Err - derived from BaseReturnCode.Err, specifically
        raised by BaseServer and its derived classes.
        """

        pass

    def __init__(self, spec: str, def_host_name: str):
        """__init__ - from the given IP/port specification, determine the
        IP:port for binding (listening) and the IP:port for connecting.

        The IP/port specification can be given in one of two forms:

          - `<ip>:<port>'
            * where the same ip address and port are used for binding and
              connecting
          - `<bind ip>:<port>;<connect ip>:<port>`
            * where a semi-colon separates the bind ip/port from the connecting
              ip/port

        In either case, a missing port (bare colon, optional) indicates the
        default port should be used. If no IP address is given, the default
        host name is used.

        No attempt is made to verify that the IP address resolves, or that it
        is reachable, though we do check they are syntactically valid.
        """
        assert (
            def_host_name
        ), f"Logic bomb!  Default host name required: {spec!r}, {def_host_name!r}"
        _spec = spec if spec else def_host_name
        parts = _spec.split(";", 1)
        pairs = []
        for part in parts:
            host_port_parts = part.rsplit(":", 1)
            if len(host_port_parts) == 1:
                port = self.def_port
            else:
                try:
                    port = int(host_port_parts[1])
                except ValueError as exc:
                    if host_port_parts[1] == "":
                        port = self.def_port
                    else:
                        raise self.Err(
                            f"Bad port specified for {self.name} in '{spec}'",
                            self.bad_port_ret_code,
                        ) from exc
            host = host_port_parts[0] if host_port_parts[0] else def_host_name
            if host[0] == "[" and host[-1] == "]":
                # Brackets are invalid for a host name, but might be used when
                # specifying a port with an IPv6 address, strip them before we
                # validate the host name.
                host = host[1:-1]
            if validate_hostname(host) != 0:
                raise self.Err(
                    f"Bad host specified for {self.name} in '{spec}'",
                    self.bad_host_ret_code,
                )
            pairs.append((host, port))

        self.bind_host, self.bind_port = pairs[0]
        if len(pairs) == 2:
            # Separate bind/connecting ip:port
            self.host, self.port = pairs[1]
            self._repr = f"{self.name} - {self.bind_host}:{self.bind_port} / {self.host}:{self.port}"
        else:
            assert len(pairs) == 1, "Logic bomb!  unexpected pairs, {pairs!r}"
            self.host, self.port = pairs[0]
            self._repr = f"{self.name} - {self.host}:{self.port}"

        self.pid_file = None

    def __repr__(self):
        return self._repr

    def kill(self, ret_val: int):
        """kill - attempt to KILL the running Redis server.

        This method is a no-op if the server instance isn't managed by us.

        Returns BaseReturnCode "enum" via the "kill" return code method.
        """
        assert self.pid_file is not None, f"Logic bomb!  Unexpected state: {self!r}"

        try:
            raw_pid = self.pid_file.read_text()
        except FileNotFoundError:
            return BaseReturnCode.kill_ret_code(BaseReturnCode.KILL_SUCCESS, ret_val)
        except OSError:
            return BaseReturnCode.kill_ret_code(BaseReturnCode.KILL_READERR, ret_val)
        except Exception:
            # No "pid" to kill
            return BaseReturnCode.kill_ret_code(BaseReturnCode.KILL_READEXC, ret_val)

        try:
            pid = int(raw_pid)
        except ValueError:
            # Bad pid value
            return BaseReturnCode.kill_ret_code(BaseReturnCode.KILL_BADPID, ret_val)

        pid_exists = True
        timeout = time.time() + 60
        while pid_exists:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pid_exists = False
            except Exception:
                # Some other error encountered trying to KILL the process.
                return BaseReturnCode.kill_ret_code(
                    BaseReturnCode.KILL_TERMEXC, ret_val
                )
            else:
                if time.time() > timeout:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    except Exception:
                        return BaseReturnCode.kill_ret_code(
                            BaseReturnCode.KILL_KILLEXC, ret_val
                        )
                    break
                time.sleep(0.1)

        # "successfully" KILL'd the give process.
        return BaseReturnCode.kill_ret_code(BaseReturnCode.KILL_SUCCESS, ret_val)


class RedisServerCommon(BaseServer):
    """RedisServerCommon - an encapsulation of the common handling of the Redis
    server specification.
    """

    def_port = def_redis_port
    bad_port_ret_code = 1
    bad_host_ret_code = 1
    name = "Redis server"
    local_host = None


def setup_logging(debug, logfile):
    """Setup logging for client
    :param debug: Turn on debug logging
    :param logfile: Logfile to write to
    """
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(message)s"

    rootLogger = logging.getLogger()
    # cause all messages to be processed when the logger is the root logger
    # or delegation to the parent when the logger is a non-root logger
    # see https://docs.python.org/3/library/logging.html
    rootLogger.setLevel(logging.NOTSET)

    streamhandler = logging.StreamHandler()
    streamhandler.setLevel(level)
    streamhandler.setFormatter(logging.Formatter(fmt))
    rootLogger.addHandler(streamhandler)

    if logfile:
        if not os.environ.get("_PBENCH_UNIT_TESTS"):
            fmt = "[%(levelname)-1s][%(asctime)s.%(msecs)d] %(message)s"
        else:
            fmt = "[%(levelname)-1s][1900-01-01T00:00:00.000000] %(message)s"
        filehandler = logging.FileHandler(logfile)
        filehandler.setLevel(logging.NOTSET)
        filehandler.setFormatter(logging.Formatter(fmt))
        rootLogger.addHandler(filehandler)

    return rootLogger


def run_command(args, env=None, name=None, logger=None):
    """Run the command defined by args and return its output"""
    try:
        output = subprocess.check_output(args=args, stderr=subprocess.STDOUT, env=env)
        if isinstance(output, bytes):
            output = output.decode("utf-8")
        return output
    except subprocess.CalledProcessError as e:
        message = "%s failed: %s" % (name, e.output)
        logger.error(message)
        raise RuntimeError(message)


def _log_date():
    """_log_data - helper function to mimick previous bash code behaviors

    Returns an ISO format date string of the current time.  If running in
    a unit test environment, returns a fixed date string.
    """
    if os.environ.get("_PBENCH_UNIT_TESTS", "0") == "1":
        log_date = "1900-01-01T00:00:00.000000"
    else:
        log_date = datetime.utcnow().isoformat()
    return log_date


def _pbench_log(message):
    """_pbench_log - helper function for logging to the ${pbench_log} file.
    """
    with open(os.environ["pbench_log"], "a+") as fp:
        print(message, file=fp)


def warn_log(msg):
    """warn_log - mimick previous bash behavior of writing warning logs to
    both stderr and the ${pbench_log} file.
    """
    message = f"[warn][{_log_date()}] {msg}"
    print(message, file=sys.stderr)
    _pbench_log(message)


def error_log(msg):
    """error_log - mimick previous bash behavior of writing error logs to
    both stderr and the ${pbench_log} file.
    """
    message = f"[error][{_log_date()}] {msg}"
    print(message, file=sys.stderr)
    _pbench_log(message)


def info_log(msg):
    """info_log - mimick previous bash behavior of writing info logs to
    the ${pbench_log} file.
    """
    message = f"[info][{_log_date()}] {msg}"
    _pbench_log(message)


def verify_sysinfo(sysinfo):
    """verify_sysinfo - given a sysinfo argument, which can be a comma
    separated list of accepted sysinfo names, verifies all the names are
    valid, expanding the short-hands for "all", "default", and "none".

    Returns two lists: the list of accepted sysinfo items, and the list of bad
    sysinfo items.
    """
    if sysinfo == "default":
        return sorted(list(sysinfo_opts_default)), []
    elif sysinfo == "all":
        return sorted(list(sysinfo_opts_available)), []
    elif sysinfo == "none":
        return [], []

    sysinfo_list = sysinfo.split(",")
    final_list = []
    bad_list = []
    for item in sysinfo_list:
        item = item.strip()
        if len(item) == 0:
            continue
        if item in sysinfo_opts_available:
            final_list.append(item)
            continue
        if item in sysinfo_opts_convenience:
            # Ignore convenience arguments
            continue
        bad_list.append(item)

    return sorted(final_list), sorted(bad_list)


def cli_verify_sysinfo(sysinfo):
    """cli_verify_sysinfo - shared method of CLI interfaces to verify the
    "sysinfo" parameter.

    Returns a tuple of the final "sysinfo" parameter list, and a list of any
    invalid sysinfo options.
    """
    if sysinfo is None:
        bad_l = []
        ret_sysinfo = ""
    else:
        sysinfo_l, bad_l = verify_sysinfo(sysinfo)
        if sysinfo_l:
            ret_sysinfo = ",".join(sysinfo_l)
        else:
            ret_sysinfo = ""
    return ret_sysinfo, bad_l


def collect_local_info(pbench_bin):
    """collect_local_info - helper method encapsulating the local information
    (metadata) about the environment where an entity is running.

    Returns a tuple of four items: the pbench agent version, build sequence
    number, and sha1 hash of the commit installed, and the array out output
    from running the hostname command with different options.
    """
    try:
        version = (pbench_bin / "VERSION").read_text().strip()
    except Exception:
        version = "(unknown)"
    try:
        seqno = (pbench_bin / "SEQNO").read_text().strip()
    except Exception:
        seqno = ""
    try:
        sha1 = (pbench_bin / "SHA1").read_text().strip()
    except Exception:
        sha1 = "(unknown)"

    hostdata = {}
    for arg in [
        "fqdn",
        "all-fqdns",
        "short",
        "alias",
        "ip-address",
        "all-ip-addresses",
        "domain",
        "nis",
    ]:
        cp = subprocess.run(
            ["hostname", f"--{arg}"],
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        hostdata[arg] = cp.stdout.strip() if cp.stdout is not None else ""

    return (version, seqno, sha1, hostdata)


if os.environ.get("_PBENCH_UNIT_TESTS"):

    class LocalRemoteHost:
        """Mock out behavior for legacy unit tests.
        """

        def __init__(self):
            self._local_names = frozenset(
                [
                    "127.0.0.1",
                    "localhost",
                    "172.16.42.42",
                    "testhost.example.com",
                    "testhost",
                ]
            )

        def is_local(self, host_name):
            return host_name in self._local_names


else:

    class LocalRemoteHost:
        """
        Provide a mechanism to determine whether a hostname is "local" (an
        alias for the current host) or "remote".
        """

        def __init__(self):
            """
            Build up a list of local IP addresses from all the interfaces.

            The IP list reported for each adapter uses the ifaddr.IP type, so
            we convert each text address into an `ipaddress` type that we can
            reliably compare. Note that this would be unnecessary in a strictly
            IPv4 environment, but IPv6 addresses cannot be compared as text.

            IPv6 addresses have additional attributes, including the "scope id"
            which defines whether an address is uniquely associated with a
            specific adapter, e.g., for a restricted subnet, or a MAC-based or
            dynamically configured link-local address. Scope IDs are
            represented with a "%scope" at the end of the IP address. Scope ID
            0 means "global" and the ID is by convention omitted; however if
            the reported IPv6 address includes a non-zero scope ID, we'll add
            it to the IP address. Linux conventionally uses the name of the NIC
            to represent the scope ID rather than the numeric index, so we'll
            use that here.

            NOTE: The Python IPv6Address parser doesn't support a scope ID
            prior to 3.9; these addresses will be rejected with a ValueError
            and we'll ignore them. This is unlikely to be a problem unless all
            communicating hosts are on a subnet with only link-local IPv6
            addresses, and not worth working around.
            """
            ips = []
            for adapter in ifaddr.get_adapters():
                for ip in adapter.ips:
                    if isinstance(ip.ip, tuple) and len(ip.ip) > 2 and ip.ip[2] != 0:
                        addr = f"{ip.ip[0]}%{adapter.name}"
                    else:
                        addr = ip.ip
                    try:
                        addr = ipaddress.ip_address(addr)
                    except ValueError:
                        # Until Python 3.9, the ipaddress parser cannot handle
                        # a scope ID. For now, we'll simply skip such addresses
                        # entirely. (It's sufficiently unlikely that we'll get
                        # an unparseable address from `ifaddr` that it's not
                        # worth trying to decode the value error here.)
                        pass
                    else:
                        ips.append(addr)
            self.aliases = frozenset(ips)

        def is_local(self, host_name):
            """
            Determine whether a given hostname is an alias for the local host; in
            other words, whether it matches a canonical representation of one of
            the routable addresses reported by `ifaddr`.

            Args:
                host_name: A hostname or IP address to check

            Returns:
                True if `host_name` matches a routable local host address
            """
            try:
                infos = socket.getaddrinfo(host_name, None)
            except socket.gaierror:
                # If address lookup fails, check whether the hostname is legal
                try:
                    addr = ipaddress.ip_address(host_name)
                    return addr in self.aliases
                except ValueError:
                    return False

            # getaddrinfo returns 5-tuples of names for the host in the format
            # (family, type, proto, name, (address, port[, flowinfo, scopeid]))
            # where flowinfo and scopeid are present only for IPv6. We want to
            # compare all IPv4 and IPv6 addresses against our list of local
            # host aliases. If any match, the given `host_name` must be a
            # representation of the local host.
            for info in infos:
                proto = info[0]
                addr = info[4]
                if proto == socket.AF_INET:
                    ip = addr[0]
                elif proto == socket.AF_INET6:
                    ip = f"{addr[0]}%{addr[3]}" if addr[3] != 0 else addr[0]
                else:  # Skip any protocol that's not IPv4 or IPv6
                    continue
                try:
                    ipaddr = ipaddress.ip_address(ip)
                    if ipaddr in self.aliases:
                        return True
                except ValueError:
                    continue
            return False
