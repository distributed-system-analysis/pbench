import pytest


def test_pbench_cli():
    command = ["pbench", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"--help" in out


def test_pbench_cli_failed():
    command = ["pbench", "--foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 2


def test_pbench_cli_version():
    command = ["pbench", "--version"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"pbench" in out
