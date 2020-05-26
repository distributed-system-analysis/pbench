import pytest


def test_pbench_avg_stddev_activate_help():
    command = ["pbench-avg-stddev", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"--help" in out


def test_pbench_avg_stddev_activate_help_invalid():
    command = ["pbench-avg-stddev", "--foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 2


def test_pbench_avg_stddev():
    command = ["pbench-avg-stddev", "1", "2", "3", "4", "5"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"3.0000 1.4142 47.1405 3\n" in out
