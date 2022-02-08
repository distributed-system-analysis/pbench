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
    iostat_default_tool = fubar_default_group / "iostat"
    iostat_default_tool.touch()

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
    assert iostat_default_tool.exists() is True


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

    fubar1_group = default_group / "fubar1.example.com"
    fubar1_group.mkdir(parents=True)
    iostat_tool = fubar1_group / "iostat"
    iostat_tool.touch()
    vmstat_tool = fubar1_group / "vmstat"
    vmstat_tool.touch()

    fubar2_group = default_group / "fubar2.example.com"
    fubar2_group.mkdir(parents=True)
    pidstat_tool = fubar2_group / "pidstat"
    pidstat_tool.touch()
    turbostat_tool = fubar2_group / "turbostat"
    turbostat_tool.touch()

    command = [
        "pbench-clear-tools",
        "--remotes=fubar1.example.com,doesnotexist.example.com," "fubar2.example.com",
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

    fubar1_group = default_group / "fubar1.example.com"
    fubar1_group.mkdir(parents=True, exist_ok=True)
    vmstat1_tool = fubar1_group / "vmstat"
    vmstat1_tool.touch()

    fubar2_group = default_group / "fubar2.example.com"
    fubar2_group.mkdir(parents=True)
    vmstat2_tool = fubar2_group / "vmstat"
    vmstat2_tool.touch()
    pidstat_tool = fubar2_group / "pidstat"
    pidstat_tool.touch()
    turbostat_tool = fubar2_group / "turbostat"
    turbostat_tool.touch()

    command = [
        "pbench-clear-tools",
        "--name=vmstat",
        "--remotes=fubar1.example.com,fubar2.example.com",
    ]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert vmstat2_tool.exists() is False
    assert vmstat1_tool.exists() is False
    assert turbostat_tool.exists() is True
    assert pidstat_tool.exists() is True


def test_clear_tools_test69(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ One tool, one remote w label, one remote w/o label, one remote w 2 tools, 1st two remotes removed """
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    default_group = pbench_run / "tools-v1-default"
    default_group.mkdir(parents=True)

    fubar1_group = default_group / "fubar1.example.com"
    fubar1_group.mkdir(parents=True, exist_ok=True)
    pidstat1_tool = fubar1_group / "pidstat"
    pidstat1_tool.touch()

    fubar2_group = default_group / "fubar2.example.com"
    fubar2_group.mkdir(parents=True, exist_ok=True)
    pidstat2_tool = fubar2_group / "pidstat"
    pidstat2_tool.touch()

    fubar3_group = default_group / "fubar3.example.com"
    fubar3_group.mkdir(parents=True, exist_ok=True)
    pidstat3_tool = fubar3_group / "pidstat"
    pidstat3_tool.touch()
    turbostat_tool = fubar3_group / "turbostat"
    turbostat_tool.touch()

    command = [
        "pbench-clear-tools",
        "--name=pidstat",
        "--remotes=fubar1.example.com,fubar2.example.com,fubar3.example.com",
    ]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert turbostat_tool.exists() is True
    assert pidstat1_tool.exists() is False
    assert pidstat2_tool.exists() is False
    assert pidstat3_tool.exists() is False


def test_clear_tools_test70(monkeypatch, agent_config, pbench_run, pbench_cfg):
    """ Attempt to clear the wrong tool, by name """
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    default_group = pbench_run / "tools-v1-default"
    default_group.mkdir(parents=True)
    fubar_host = default_group / "fubar.example.com"
    fubar_host.mkdir(parents=True, exist_ok=True)
    pidstat_tool = fubar_host / "pidstat"
    pidstat_tool.touch()

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

    command = ["pbench-clear-tools", "--groups=default,another"]
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
    fubar_another_host = another_group / "fubar.example.com"
    fubar_another_host.mkdir(parents=True, exist_ok=True)
    pidstat_another_tool = fubar_another_host / "pidstat"
    pidstat_another_tool.touch()

    command = ["pbench-clear-tools", "--groups=another,wrong"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    assert (
        b'Removed "pidstat" from host "fubar.example.com" in tools group '
        b'"another"' in err
    )
    assert b'pbench-clear-tools: invalid --group option "wrong"' in err
    assert another_group.exists() is False


@pytest.mark.parametrize(
    "groups", ["default", "default,custom1", "default,custom1,custom2"]
)
@pytest.mark.parametrize(
    "remotes",
    ["remote1", "remote1,remote2", "remote1,remote2,remote3", "remote2,remote4"],
)
@pytest.mark.parametrize(
    "tools", ["pidstat", "pidstat,mpstat", "pidstat,mpstat,iostat", "mpstat," "vmstat"]
)
def test_clear_tools_test73(
    monkeypatch, tmp_path, agent_config, pbench_run, pbench_cfg, groups, remotes, tools
):
    """ Attempt to clear the tools, by name, separated by comma"""
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    tools_existence = []
    for group in groups.split(","):
        custom_group = pbench_run / f"tools-v1-{group}"
        custom_group.mkdir(parents=True)
        for remote in remotes.split(","):
            remote_host = custom_group / f"{remote}.example.com"
            remote_host.mkdir(parents=True, exist_ok=True)
            for tool in tools.split(","):
                tool_file = remote_host / tool
                tool_file.touch()
                tools_existence.append(tool_file)

    command = ["pbench-clear-tools", "--name=pidstat,mpstat"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    assert b"" in err
    for tool in tools_existence:
        tool_str = str(tool).replace(str(tmp_path), "")
        if any(x in tool_str for x in ["pidstat", "mpstat"]) and "default" in tool_str:
            assert tool.exists() is False
        else:
            assert tool.exists() is True

    command = [
        "pbench-clear-tools",
        "--groups=custom1,custom2",
        "--name=pidstat,mpstat",
    ]
    # By this point pidstat and mpstat tools in all groups should be cleared
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    assert b"" in err
    for tool in tools_existence:
        tool_str = str(tool).replace(str(tmp_path), "")
        if any(x in tool_str for x in ["pidstat", "mpstat"]):
            assert tool.exists() is False
        else:
            assert tool.exists() is True


@pytest.mark.parametrize(
    "remotes",
    [
        "remote1",
        "remote1,remote2",
        "remote1,remote2,remote3",
        "remote2,remote4",
        "remote4,remote2,remote5",
    ],
)
def test_clear_tools_test74(monkeypatch, agent_config, pbench_run, pbench_cfg, remotes):
    """ Attempt to clear all tools in default group, by name, separated by
    comma"""
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
    default_group = pbench_run / "tools-v1-default"
    default_group.mkdir(parents=True)
    tools_existence = []
    for remote in remotes.split(","):
        remote_host = default_group / f"{remote}.example.com"
        remote_host.mkdir(parents=True, exist_ok=True)
        pidstat_tool = remote_host / "pidstat"
        pidstat_tool.touch()
        tools_existence.append(pidstat_tool)
        mpstat_tool = remote_host / "mpstat"
        mpstat_tool.touch()
        tools_existence.append(mpstat_tool)
        iostat_tool = remote_host / "iostat"
        iostat_tool.touch()
        tools_existence.append(iostat_tool)

    command = [
        "pbench-clear-tools",
        "--remote=remote1.example.com",
        "--name=pidstat,mpstat,iostat",
    ]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    for tool in tools_existence:
        if any(x in str(tool) for x in ["remote1.example.com"]):
            assert tool.exists() is False
        else:
            assert tool.exists() is True

    command = [
        "pbench-clear-tools",
        "--remotes=remote2.example.com,remote3.example.com",
        "--name=pidstat,mpstat,iostat",
    ]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    for tool in tools_existence:
        if any(
            x in str(tool)
            for x in [
                "remote1.example.com",
                "remote2.example.com",
                "remote3.example.com",
            ]
        ):
            assert tool.exists() is False
        else:
            assert tool.exists() is True

    command = ["pbench-clear-tools", "--name=pidstat,mpstat,iostat"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    for tool in tools_existence:
        assert tool.exists() is False


@pytest.mark.parametrize("groups", ["custom1", "custom1,custom2"])
@pytest.mark.parametrize("remotes", ["remote1", "remote1,remote2"])
def test_clear_tools_test75(
    monkeypatch, agent_config, pbench_run, pbench_cfg, groups, remotes
):
    """ Attempt to clear all tools in non-default groups, by name, separated by
        comma"""
    groups_shouldnt_exists = []
    for group in groups.split(","):
        another_group = pbench_run / f"tools-v1-{group}"
        another_group.mkdir(parents=True)
        groups_shouldnt_exists.append(another_group)
        for remote in remotes:
            remote_host = another_group / f"{remote}.example.com"
            remote_host.mkdir(parents=True, exist_ok=True)
            pidstat7_tool = remote_host / "pidstat"
            pidstat7_tool.touch()
            mpstat7_tool = remote_host / "mpstat"
            mpstat7_tool.touch()

    command = ["pbench-clear-tools", f"--group={groups}", "--name=pidstat,mpstat"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    for group in groups_shouldnt_exists:
        assert group.exists() is False


@pytest.mark.parametrize(
    "groups", ["default", "default,custom1", "default,custom1,custom2"]
)
@pytest.mark.parametrize(
    "remotes",
    ["remote1", "remote1,remote2", "remote1,remote2,remote3", "remote2,remote4"],
)
def test_clear_tools_test76(
    monkeypatch, agent_config, pbench_run, pbench_cfg, groups, remotes
):
    """ Attempt to clear groups, by name, registered on multiple
    hosts"""
    tools_existence = []
    for group in groups.split(","):
        another_group = pbench_run / f"tools-v1-{group}"
        another_group.mkdir(parents=True)

        for remote in remotes.split(","):
            fubar7_1_host = another_group / f"{remote}.example.com"
            fubar7_1_host.mkdir(parents=True, exist_ok=True)
            pidstat7_1_tool = fubar7_1_host / "pidstat"
            pidstat7_1_tool.touch()
            tools_existence.append(pidstat7_1_tool)

    command = [
        "pbench-clear-tools",
        f"--group={groups}",
        "--remote=remote2.example.com,remote3.example.com",
    ]
    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out
    for tool in tools_existence:
        if any(x in str(tool) for x in ["remote2.example.com", "remote3.example.com"]):
            assert tool.exists() is False
        else:
            assert tool.exists() is True
