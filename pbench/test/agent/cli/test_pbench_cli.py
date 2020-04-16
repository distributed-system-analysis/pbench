from pbench.test.agent.cli.conftest import capture


def test_pbench_cli():
    command = ["pbench"]
    out, err, exitcode = capture(command)
    assert exitcode == 0


def test_pbench_config_help():
    command = ["pbench", "--help"]
    out, err, exitcode = capture(command)
    print(err)
    assert b"--help" in out
    assert exitcode == 0
