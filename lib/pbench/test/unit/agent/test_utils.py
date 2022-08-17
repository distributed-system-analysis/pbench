"""Tests for the utils module.
"""
import os
import signal
import socket
import time

import ifaddr
import pytest

from pbench.agent.utils import BaseServer, BaseReturnCode, LocalRemoteHost


class OurServer(BaseServer):
    def_port = 4242
    bad_port_ret_code = 42
    bad_host_ret_code = 43
    name = "forty-two"


class TestBaseServer:
    """Verify the utils BaseServer class."""

    def test_constructor(self):
        with pytest.raises(AssertionError):
            bs = OurServer("", "")

        for arg1, arg2 in [("", "localhost"), ("localhost", "localhost")]:
            bs = OurServer(arg1, arg2)
            assert bs.pid_file is None
            assert bs.host == "localhost"
            assert bs.port == OurServer.def_port
            assert bs.bind_host == bs.host
            assert bs.bind_port == bs.port
            assert repr(bs) == f"forty-two - localhost:{OurServer.def_port:d}"

        _def = "localhost"

        with pytest.raises(OurServer.Err) as excinfo:
            bs = OurServer("bad_host.example.com", _def)
        assert (
            excinfo.value.return_code == OurServer.bad_host_ret_code
        ), f"{excinfo.value!r}"

        with pytest.raises(OurServer.Err) as excinfo:
            bs = OurServer("bad-port.example.com:bad", _def)
        assert (
            excinfo.value.return_code == OurServer.bad_port_ret_code
        ), f"{excinfo.value!r}"

        for arg1, exp_port in [
            ("host.example.com:2345", 2345),
            ("host.example.com:", 4242),
        ]:
            bs = OurServer(arg1, _def)
            assert bs.pid_file is None
            assert bs.host == "host.example.com"
            assert bs.port == exp_port
            assert bs.bind_host == bs.host
            assert bs.bind_port == bs.port
            assert repr(bs) == f"forty-two - host.example.com:{exp_port:d}"

        bs = OurServer(":2345", _def)
        assert bs.pid_file is None
        assert bs.host == "localhost"
        assert bs.port == 2345
        assert bs.bind_host == bs.host
        assert bs.bind_port == bs.port
        assert repr(bs) == "forty-two - localhost:2345"

        bs = OurServer("127.0.0.42:4567", _def)
        assert bs.pid_file is None
        assert bs.host == "127.0.0.42"
        assert bs.port == 4567
        assert bs.bind_host == bs.host
        assert bs.bind_port == bs.port
        assert repr(bs) == "forty-two - 127.0.0.42:4567"

        bs = OurServer("[127::42]:4567", _def)
        assert bs.pid_file is None
        assert bs.host == "127::42"
        assert bs.port == 4567
        assert bs.bind_host == bs.host
        assert bs.bind_port == bs.port
        assert repr(bs) == "forty-two - 127::42:4567"

        bs = OurServer("bind.example.com:2345;host.example.com:6789", _def)
        assert bs.pid_file is None
        assert bs.host == "host.example.com"
        assert bs.port == 6789
        assert bs.bind_host == "bind.example.com"
        assert bs.bind_port == 2345
        assert repr(bs) == "forty-two - bind.example.com:2345 / host.example.com:6789"

    def test_kill(self, tmp_path, monkeypatch):
        bs = OurServer("localhost", "localhost")
        with pytest.raises(AssertionError):
            bs.kill(1)

        pidfile = tmp_path / "test.pid"

        bs = OurServer("localhost", "localhost")
        bs.pid_file = pidfile
        pidfile.write_text("badpid")
        ret = bs.kill(42)
        assert ret == (BaseReturnCode.KILL_BADPID * 100) + 42

        bs = OurServer("localhost", "localhost")
        bs.pid_file = tmp_path / "enoent.pid"
        ret = bs.kill(42)
        assert ret == 42

        class MockPath:
            def __init__(self, exc: Exception):
                self._exc = exc

            def read_text(self):
                raise self._exc

        bs = OurServer("localhost", "localhost")
        bs.pid_file = MockPath(OSError(13, "fake oserror"))
        ret = bs.kill(42)
        assert ret == 342

        bs = OurServer("localhost", "localhost")
        bs.pid_file = MockPath(Exception("fake exception"))
        ret = bs.kill(42)
        assert ret == 142

        class MockTime:
            def __init__(self):
                self._clock = 0

            def time(self, *args, **kwargs):
                self._clock += 1
                return self._clock

            def sleep(self, *args, **kwargs):
                return

        class MockKill:
            behaviors = {
                "1001": (True, False, True, False, False, False),
                "1002": (False, False, False, False, False, False),
                "1003": (True, True, False, True, False, False),
                "1004": (True, False, False, True, False, False),
                "1005": (True, False, False, False, True, False),
                "1006": (True, False, False, False, False, True),
            }

            def __init__(self, behavior):
                (
                    self.pid_exists_term,
                    self.pid_exists_kill,
                    self.pid_killed_by_term,
                    self.pid_killed_by_kill,
                    self.pid_kill_term_exc,
                    self.pid_kill_kill_exc,
                ) = self.behaviors[behavior]

            def kill(self, pid, sig):
                if sig == signal.SIGTERM:
                    if self.pid_kill_term_exc:
                        raise Exception("term")
                    if self.pid_exists_term:
                        if self.pid_killed_by_term:
                            self.pid_exists_term = False
                            self.pid_exists_kill = False
                    else:
                        raise ProcessLookupError(pid)
                else:
                    assert sig == signal.SIGKILL
                    if self.pid_kill_kill_exc:
                        raise Exception("kill")
                    if self.pid_exists_kill:
                        if self.pid_killed_by_kill:
                            self.pid_exists_term = False
                            self.pid_exists_kill = False
                    else:
                        raise ProcessLookupError(pid)

        test_cases = [
            ("1001", 42, "Kill a pid that is found, successfully"),
            ("1002", 42, "Kill a pid that is not found, successfully"),
            (
                "1003",
                42,
                "Kill a pid that is found, successfully,"
                " where the SIGKILL successfully kills it",
            ),
            (
                "1004",
                42,
                "Kill a pid that is found, unsuccessfully,"
                " where the SIGKILL does not find it",
            ),
            ("1005", 442, "Exception raised killing a pid w TERM"),
            ("1006", 542, "Exception raised killing a pid w KILL"),
        ]
        for pid_text, ret_code, desc in test_cases:
            bs = OurServer("localhost", "localhost")
            bs.pid_file = pidfile
            pidfile.write_text(pid_text)
            mock_time = MockTime()
            mock_kill = MockKill(pid_text)
            monkeypatch.setattr(os, "kill", mock_kill.kill)
            monkeypatch.setattr(time, "time", mock_time.time)
            monkeypatch.setattr(time, "sleep", mock_time.sleep)
            ret = bs.kill(42)
            assert ret == ret_code, f"{desc} FAILED, {pid_text!r}, {ret_code!r}"


class TestLocalRemoteHost:
    """Verify LocalRemoteHost class works as expected."""

    @staticmethod
    def test_methods(monkeypatch):
        monkeypatch.setattr(
            "ifaddr.get_adapters",
            lambda: [
                ifaddr.Adapter(
                    "lo",
                    "lo",
                    [
                        ifaddr.IP("127.0.0.1", 8, "lo"),
                        ifaddr.IP(("::1", 0, 0), 128, "lo"),
                    ],
                    1,
                ),
                ifaddr.Adapter(
                    "eth0",
                    "eth0",
                    [
                        ifaddr.IP("10.1.1.1", 255, "eth0"),
                        ifaddr.IP(("2600::1", 0, 0), 64, "eth0"),
                        ifaddr.IP(("fe80::1", 0, 2), 64, "eth0"),
                    ],
                    2,
                ),
            ],
        )
        lrh = LocalRemoteHost()

        # An unresolvable host isn't usable for benchmarking; we expect name
        # resolution to fail, and the exception should propagate to the caller.
        with pytest.raises(socket.gaierror):
            lrh.is_local("testhost.example.com")
        assert not lrh.is_local("example.com"), "'example.com' should be remote"
        assert lrh.is_local("localhost"), "'localhost' should be local"
        assert not lrh.is_local("1.0.0.1"), "'1.0.0.1' should be remote"
        assert lrh.is_local("127.0.0.1"), "'127.0.0.1' should be local"
        assert lrh.is_local("::1"), "'::1' should be local"
        assert lrh.is_local("2600::1"), "'2600::1' should be local"
        assert lrh.is_local("2600::0:0:1"), "'2600::0:0:1' should be local"
        assert not lrh.is_local("2600::3"), "'2600::3' should be remote"
