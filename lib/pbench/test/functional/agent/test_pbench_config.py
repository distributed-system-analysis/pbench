import pytest

from pbench.test.unit.agent.conftest import valid_config, agent_config_env  # noqa F401


def test_pbench_config():
    command = ["pbench-config"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 1


def test_pbench_config_help():
    command = ["pbench-config", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert out.decode("UTF-8").startswith("Usage: pbench-config ")
    assert exitcode == 0


def test_pbench_agent_config(valid_config, agent_config_env, pytestconfig):  # noqa F811
    TMP = pytestconfig.cache.get("TMP", None)
    command = ["pbench-config", "pbench_run", "pbench-agent"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert f"{TMP}/var/lib/pbench-agent".encode("UTF-8") in out
    assert (
        exitcode == 0
    ), f"command, '{command}', failed: {exitcode:d}; out={out!r}, err={err!r}"
