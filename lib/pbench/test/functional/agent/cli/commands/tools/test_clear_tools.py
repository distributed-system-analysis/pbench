import pytest


def test_pbench_clear_tools_help():
    command = ["pbench-clear-tools", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"Usage: pbench-clear-tools [OPTIONS]" in out
    assert exitcode == 0


def test_clear_tools_test12(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """Remove all tools from all tool groups"""
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    default_group = pbench_run / "tools-v1-default" / "testhost.example.com"
    default_group.mkdir(parents=True)
    foo_group = pbench_run / "tools-v1-default" / "fubar"
    foo_group.mkdir(parents=True)
    mpstat = default_group / "mpstat"
    mpstat.touch()

    command = ["pbench-clear-tools"]
    err, out, exitcode = pytest.helpers.capture(command)
    assert b'All tools removed from host, "testhost.example.com"' in out
    assert exitcode == 0
    assert mpstat.exists() is False
    assert default_group.exists() is False
    assert foo_group.exists() is False


def test_clear_tools_test13(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """Remove one tool group leaving the default"""
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    default_group = pbench_run / "tools-v1-default" / "testhost.example.com"
    default_group.mkdir(parents=True)
    default_mpstat = default_group / "mpstat"
    default_mpstat.touch()
    foo_group = pbench_run / "tools-v1-default" / "fubar2"
    foo_group.mkdir(parents=True)
    foo_mpstat = foo_group / "mpstat"

    command = ["pbench-clear-tools", "--remote=fubar2"]
    err, out, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert default_mpstat.exists() is True
    assert foo_mpstat.exists() is False


def test_clear_tools_test65(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ Remove all tools from group good, leave default alone """
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    good_group = pbench_run / "tools-v1-good"
    for host in ["fubar2", "fubar", "testhost.example.com"]:
        (good_group / host).mkdir(parents=True)
    iostat_tool = good_group / "fubar" / "iostat"
    iostat_tool.touch()
    vmstat_tool = good_group / "fubar" / "vmstat"
    vmstat_tool.touch()
    pidstat_tool = good_group / "fubar2" / "pidstat"
    pidstat_tool.touch()
    turbostat_tool = good_group / "fubar2" / "turbostat"
    turbostat_tool.touch()
    mpstat_tool = good_group / "testhost.example.com" / "mpstat"
    mpstat_tool.touch()

    command = ["pbench-clear-tools", "--group=good"]
    err, out, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert iostat_tool.exists() is False
    assert vmstat_tool.exists() is False
    assert pidstat_tool.exists() is False
    assert turbostat_tool.exists() is False
    assert mpstat_tool.exists() is False
    assert good_group.exists() is True


def test_clear_tools_test66(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ Error group does not exist """
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    command = ["pbench-clear-tools", "--group=bad"]
    err, out, exitcode = pytest.helpers.capture(command)
    assert exitcode == 1
    assert b"\tpbench-clear-tools: invalid" in err


def test_clear_tools_test67(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ Remove all tools from 2 remotes, one remote does not exist """
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    default_group = pbench_run / "tools-v1-default"
    default_group.mkdir(parents=True)

    fubar3_group = default_group / "fubar3.example.com"
    fubar3_group.mkdir(parents=True)
    iostat_tool = fubar3_group / "iostat"
    iostat_tool.touch()
    vmstat_tool = fubar3_group / "vmstat"
    vmstat_tool.touch()

    fubar4_group = default_group / "fubar4.example.com"
    fubar4_group.mkdir(parents=True)
    pidstat_tool = fubar4_group / "pidstat"
    pidstat_tool.touch()
    turbostat_tool = fubar4_group / "turbostat"
    turbostat_tool.touch()

    command = [
        "pbench-clear-tools",
        "--remotes=fubar3.example.com,doesnotexist.example.com,fubar4.example.com",
    ]
    err, out, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert (
        b'The given remote host, "doesnotexist.example.com", is not a directory in'
        in out
    )
    assert iostat_tool.exists() is False
    assert vmstat_tool.exists() is False
    assert pidstat_tool.exists() is False
    assert turbostat_tool.exists() is False


def test_clear_tools_test68(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ Remove one tool from two remotes, remotes not removed """
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    default_group = pbench_run / "tools-v1-default"
    default_group.mkdir(parents=True)

    fubar5_group = default_group / "fubar5.example.com"
    fubar5_group.mkdir(parents=True, exist_ok=True)
    vmstat5_tool = fubar5_group / "vmstat"
    vmstat5_tool.touch()

    fubar6_group = default_group / "fubar6.example.com"
    fubar6_group.mkdir(parents=True)
    vmstat6_tool = fubar6_group / "vmstat"
    vmstat6_tool.touch()
    pidstat_tool = fubar6_group / "pidstat"
    pidstat_tool.touch()
    turbostat_tool = fubar6_group / "turbostat"
    turbostat_tool.touch()

    command = [
        "pbench-clear-tools",
        "--name=vmstat",
        "--remotes=fubar5.example.com,fubar6.example.com",
    ]
    err, out, exitcode = pytest.helpers.capture(command)
    assert vmstat6_tool.exists() is False
    assert vmstat5_tool.exists() is False
    assert turbostat_tool.exists() is True
    assert pidstat_tool.exists() is True
    assert exitcode == 0


def test_clear_tools_test69(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ One tool, one remote w label, one remote w/o label, one remote w 2 tools, 1st two remotes removed """
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    default_group = pbench_run / "tools-v1-default"
    default_group.mkdir(parents=True)

    fubar5_group = default_group / "fubar5.example.com"
    fubar5_group.mkdir(parents=True, exist_ok=True)
    pidstat5_tool = fubar5_group / "pidstat"
    pidstat5_tool.touch()

    fubar6_group = default_group / "fubar6.example.com"
    fubar6_group.mkdir(parents=True, exist_ok=True)
    pidstat6_tool = fubar6_group / "pidstat"
    pidstat6_tool.touch()

    fubar7_group = default_group / "fubar7.example.com"
    fubar7_group.mkdir(parents=True, exist_ok=True)
    pidstat7_tool = fubar7_group / "pidstat"
    pidstat7_tool.touch()
    turbostat_tool = fubar7_group / "turbostat"
    turbostat_tool.touch()

    command = [
        "pbench-clear-tools",
        "--name=pidstat",
        "--remotes=fubar5.example.com,fubar6.example.com,fubar7.example.com",
    ]
    err, out, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert turbostat_tool.exists() is True
    assert pidstat5_tool.exists() is False
    assert pidstat6_tool.exists() is False
    assert pidstat7_tool.exists() is False
