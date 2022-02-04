import pytest


def test_pbench_clear_tools_help():
    command = ["pbench-clear-tools", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"Usage: pbench-clear-tools [OPTIONS]" in out
    assert b"" == err
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
    out, err, exitcode = pytest.helpers.capture(command)
    assert (
        b'All tools removed from group "default" on host "testhost.example.com"' in err
    )
    assert b"" == out
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
    foo_mpstat.touch()

    command = ["pbench-clear-tools", "--remote=fubar2"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b'Removed "mpstat" from host "fubar2" in tools group "default"' in err
    assert b"" == out
    assert exitcode == 0
    assert default_mpstat.exists() is True
    assert foo_mpstat.exists() is False


def test_clear_tools_test65(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ Remove all tools from group good, leave default alone """
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    default_group = pbench_run / "tools-v1-default"
    fubar_default_group = default_group / "fubar2.example.com"
    fubar_default_group.mkdir(parents=True)

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
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert iostat_tool.exists() is False
    assert vmstat_tool.exists() is False
    assert pidstat_tool.exists() is False
    assert turbostat_tool.exists() is False
    assert mpstat_tool.exists() is False
    assert good_group.exists() is False
    assert fubar_default_group.exists() is True


def test_clear_tools_test66(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ Error group does not exist """
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    command = ["pbench-clear-tools", "--group=bad"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    assert b'pbench-clear-tools: invalid --group option "bad"' in err
    assert exitcode == 1


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
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    assert b'No remote host "doesnotexist.example.com" in group default' in err
    assert exitcode == 0
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
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert vmstat6_tool.exists() is False
    assert vmstat5_tool.exists() is False
    assert turbostat_tool.exists() is True
    assert pidstat_tool.exists() is True


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
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert turbostat_tool.exists() is True
    assert pidstat5_tool.exists() is False
    assert pidstat6_tool.exists() is False
    assert pidstat7_tool.exists() is False


def test_clear_tools_test70(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ Attempt to clear the wrong tool, by name """
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    default_group = pbench_run / "tools-v1-default"
    default_group.mkdir(parents=True)
    fubar5_host = default_group / "fubar5.example.com"
    fubar5_host.mkdir(parents=True, exist_ok=True)
    pidstat5_tool = fubar5_host / "pidstat"
    pidstat5_tool.touch()

    command = ["pbench-clear-tools", "--name=vmstat"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    assert b"Tools ['vmstat'] not found in group default\n" in err
    assert exitcode == 0


def test_clear_tools_test71(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ Attempt to clear the tool groups, by name, separated by comma"""
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    default_group = pbench_run / "tools-v1-default"
    default_group.mkdir(parents=True)
    fubar_default_host = default_group / "fubar6.example.com"
    fubar_default_host.mkdir(parents=True, exist_ok=True)
    pidstat_default_tool = fubar_default_host / "pidstat"
    pidstat_default_tool.touch()

    another_group = pbench_run / "tools-v1-another"
    another_group.mkdir(parents=True)
    fubar_another_host = another_group / "fubar7.example.com"
    fubar_another_host.mkdir(parents=True, exist_ok=True)
    pidstat_another_tool = fubar_another_host / "pidstat"
    pidstat_another_tool.touch()

    command = ["pbench-clear-tools", "--group=default,another"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    assert default_group.exists() is True
    assert another_group.exists() is False


def test_clear_tools_test72(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ Attempt to clear the tool groups, by name, separated by comma.
    However one of the tool group name is wrong"""
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))

    another_group = pbench_run / "tools-v1-another"
    another_group.mkdir(parents=True)
    fubar_another_host = another_group / "fubar7.example.com"
    fubar_another_host.mkdir(parents=True, exist_ok=True)
    pidstat_another_tool = fubar_another_host / "pidstat"
    pidstat_another_tool.touch()

    command = ["pbench-clear-tools", "--group=another,wrong"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    assert (
        b'Removed "pidstat" from host "fubar7.example.com" in tools group '
        b'"another"' in err
    )
    assert b'pbench-clear-tools: invalid --group option "wrong"' in err
    assert another_group.exists() is False


def test_clear_tools_test73(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ Attempt to clear the tools, by name, separated by comma"""
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    default_group = pbench_run / "tools-v1-default"
    default_group.mkdir(parents=True)
    fubar6_host = default_group / "fubar6.example.com"
    fubar6_host.mkdir(parents=True, exist_ok=True)
    pidstat6_tool = fubar6_host / "pidstat"
    pidstat6_tool.touch()
    mpstat6_tool = fubar6_host / "mpstat"
    mpstat6_tool.touch()
    iostat6_tool = fubar6_host / "iostat"
    iostat6_tool.touch()

    command = ["pbench-clear-tools", "--name=pidstat,mpstat"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    assert b"" in err
    assert pidstat6_tool.exists() is False
    assert mpstat6_tool.exists() is False
    assert iostat6_tool.exists() is True


def test_clear_tools_test74(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ Attempt to clear all tools in default group, by name, separated by
    comma"""
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    default_group = pbench_run / "tools-v1-default"
    default_group.mkdir(parents=True)
    fubar6_host = default_group / "fubar6.example.com"
    fubar6_host.mkdir(parents=True, exist_ok=True)
    pidstat6_tool = fubar6_host / "pidstat"
    pidstat6_tool.touch()
    mpstat6_tool = fubar6_host / "mpstat"
    mpstat6_tool.touch()
    iostat6_tool = fubar6_host / "iostat"
    iostat6_tool.touch()

    command = ["pbench-clear-tools", "--name=pidstat,mpstat,iostat"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    assert pidstat6_tool.exists() is False
    assert mpstat6_tool.exists() is False
    assert iostat6_tool.exists() is False
    assert fubar6_host.exists() is False
    assert default_group.exists() is True


def test_clear_tools_test75(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ Attempt to clear all tools in non-default group, by name, separated by
        comma"""
    another_group = pbench_run / "tools-v1-another"
    another_group.mkdir(parents=True)
    fubar7_host = another_group / "fubar7.example.com"
    fubar7_host.mkdir(parents=True, exist_ok=True)
    pidstat7_tool = fubar7_host / "pidstat"
    pidstat7_tool.touch()
    mpstat7_tool = fubar7_host / "mpstat"
    mpstat7_tool.touch()

    command = ["pbench-clear-tools", "--group=another", "--name=pidstat,mpstat"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    assert another_group.exists() is False


def test_clear_tools_test76(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ Attempt to clear a group, by name, registered on multiple
    hosts"""
    another_group = pbench_run / "tools-v1-another"
    another_group.mkdir(parents=True)

    fubar7_1_host = another_group / "fubar7_1.example.com"
    fubar7_1_host.mkdir(parents=True, exist_ok=True)
    pidstat7_1_tool = fubar7_1_host / "pidstat"
    pidstat7_1_tool.touch()

    fubar7_2_host = another_group / "fubar7_2.example.com"
    fubar7_2_host.mkdir(parents=True, exist_ok=True)
    pidstat7_2_tool = fubar7_2_host / "pidstat"
    pidstat7_2_tool.touch()

    command = ["pbench-clear-tools", "--group=another", "--remote=fubar7_2.example.com"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    assert pidstat7_1_tool.exists() is True
    assert fubar7_2_host.exists() is False
