import pytest


def test_pbench_log_timestamp():
    command = ["pbench-log-timestamp", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"Usage: pbench-log-timestamp [OPTIONS]" in out
    assert exitcode == 0
