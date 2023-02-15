"""Test wait_for_uri() module method"""
from contextlib import contextmanager
import socket

import pytest

import pbench.common
from pbench.common.exceptions import BadConfig


def test_wait_for_uri_succ(monkeypatch):
    called = [None]

    @contextmanager
    def success(*args, **kwargs):
        called[0] = args
        yield None

    monkeypatch.setattr(socket, "create_connection", success)
    pbench.common.wait_for_uri("http://localhost:42", 142)
    first_arg = called[0][0]
    assert first_arg[0] == "localhost" and first_arg[1] == 42, f"{called[0]!r}"


def test_wait_for_uri_bad():
    with pytest.raises(BadConfig) as exc:
        pbench.common.wait_for_uri("http://:42", 142)
    assert str(exc.value).endswith("host name")

    with pytest.raises(BadConfig) as exc:
        pbench.common.wait_for_uri("http://example.com", 142)
    assert str(exc.value).endswith("port number")


def setup_conn_ref(monkeypatch):
    clock = [0]
    called = []

    @contextmanager
    def conn_ref(*args, **kwargs):
        called.append(f"conn_ref [{clock[0]}]")
        if clock[0] < 3:
            raise ConnectionRefusedError()
        yield None

    def sleep(*args, **kwargs):
        called.append("sleep")

    def time() -> int:
        curr_time = clock[0]
        clock[0] += 1
        return curr_time

    monkeypatch.setattr(socket, "create_connection", conn_ref)
    monkeypatch.setattr(pbench.common, "sleep", sleep)
    monkeypatch.setattr(pbench.common, "time", time)
    return called


def test_wait_for_uri_conn_ref_succ(monkeypatch):
    called = setup_conn_ref(monkeypatch)
    pbench.common.wait_for_uri("http://localhost:42", 42)
    assert called == [
        "conn_ref [1]",
        "sleep",
        "conn_ref [2]",
        "sleep",
        "conn_ref [3]",
    ], f"{called!r}"


def test_wait_for_uri_conn_ref_fail(monkeypatch):
    called = setup_conn_ref(monkeypatch)
    with pytest.raises(ConnectionRefusedError):
        pbench.common.wait_for_uri("http://localhost:42", 1)
    assert called == [
        "conn_ref [1]",
        "sleep",
        "conn_ref [2]",
    ], f"{called!r}"
