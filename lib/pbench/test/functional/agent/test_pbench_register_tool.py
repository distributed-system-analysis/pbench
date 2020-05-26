import pytest


def test_pbench_register_tool_activate_help():
    command = ["pbench-register-tool", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"--help" in out


def test_pbench_register_tool_activate_help_failed():
    command = ["pbench-register-tool", "--foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 2


def test_pbench_register_tool_missing_scripts(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    command = ["pbench-register-tool", "--name", "perf"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"Could not find" in out
    assert exitcode == 1


def test_pbench_register_tool_default(
    tmpdir,
    create_agent_environment,
    pbench_run,
    pbench_conf,
    monkeypatch,
    install_tool_scripts,
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    command = ["pbench-register-tool", "--name", "perf"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    perf = pbench_run / "tools-default" / "perf"
    assert b"perf: perf is installed" in out
    assert perf.exists() is True


def test_pbench_register_tool_with_group(
    tmpdir,
    create_agent_environment,
    pbench_run,
    pbench_conf,
    monkeypatch,
    install_tool_scripts,
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    command = ["pbench-register-tool", "--name", "perf", "--group", "foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    perf = pbench_run / "tools-foo" / "perf"
    assert b"perf: perf is installed" in out
    assert perf.exists() is True


def test_pbench_register_tool_unknown_tool(
    tmpdir,
    create_agent_environment,
    pbench_run,
    pbench_conf,
    monkeypatch,
    install_tool_scripts,
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    # (zul): if you create a tool called foo this test needs to be updated ;-)
    command = ["pbench-register-tool", "--name", "foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"Could not find" in out
    assert exitcode == 1
    perf = pbench_run / "tools-default" / "perf"
    assert perf.exists() is False


def test_pbench_register_tool_with_args(
    tmpdir,
    create_agent_environment,
    pbench_run,
    pbench_conf,
    monkeypatch,
    install_tool_scripts,
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    command = ["pbench-register-tool", "--name", "disk", "--", "--interval=42"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"disk is registered" in out
    assert exitcode == 0
    disk = pbench_run / "tools-default" / "disk"
    assert disk.exists() is True
    assert "interval" in disk.read_text(encoding="utf-8")
