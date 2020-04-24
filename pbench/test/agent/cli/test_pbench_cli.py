from pbench.test.agent.cli.conftest import capture


def test_pbench_cli():
    command = ["pbench"]
    out, err, exitcode = capture(command)
    assert exitcode == 0, f"out={out!r} err={err!r}"


def test_pbench_config_help():
    command = ["pbench", "--help"]
    out, err, exitcode = capture(command)
    assert b"--help" in out, f"out={out!r} err={err!r}"
    assert exitcode == 0, f"out={out!r} err={err!r}"
