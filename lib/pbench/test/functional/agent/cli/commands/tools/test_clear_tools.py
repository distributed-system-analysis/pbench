import pytest


@pytest.fixture
def tools_configuration(monkeypatch, agent_config, pbench_run, pbench_cfg):
    tree = {
        "default": {
            "remote1": ["pidstat"],
            "remote2": ["mpstat"],
            "remote3": ["pidstat", "turbostat"],
        },
        "group1": {"remote1": ["mpstat"]},
        "group3": {"remote3": ["pidstat", "mpstat"]},
    }
    tools_existence = []

    for group, remotes in tree.items():
        gd = pbench_run / f"tools-v1-{group}"
        gd.mkdir(parents=True)

        for remote, tools in remotes.items():
            rd = gd / f"{remote}.example.com"
            rd.mkdir(parents=True)

            for tool in tools:
                t = rd / tool
                t.touch()
                tools_existence.append(t)

    return tools_existence, tree


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
    assert (
        b"Tools ['vmstat'] not found in remote fubar.example.com and group "
        b"default\n" in err
    )
    assert exitcode == 0


@pytest.mark.parametrize(
    "groups",
    [
        "",
        "default",
        "default,group1",
        ",default,,,group1,",
        "default,group1,group2",
        "group1,group2,group3",
    ],
)
@pytest.mark.parametrize(
    "remotes",
    [
        "",
        "remote1",
        "remote1,remote2",
        ",remote1,,,remote2,",
        "remote1,remote2,remote3",
        "remote2,remote4",
    ],
)
@pytest.mark.parametrize(
    "tools",
    [
        "",
        "pidstat",
        "pidstat,mpstat",
        ",pidstat,,mpstat,",
        "pidstat,mpstat,iostat",
        "mpstat,vmstat",
    ],
)
def test_clear_tools_test85(pbench_run, tools_configuration, groups, remotes, tools):
    """ Attempt to clear tools with various combinations of groups, remotes
    and tools against fixed tools configuration"""
    tools_existence, tools_tree = tools_configuration

    command = ["pbench-clear-tools"]
    if groups:
        command.append(f"--groups={groups}")
    if remotes:
        command.append(
            f"--remotes={','.join(map(lambda x: f'{x}.example.com' if x else x, remotes.split(',')))}"
        )
    if tools:
        command.append(f"--name={tools}")

    out, err, exitcode = pytest.helpers.capture(command)

    assert b"" == out
    for tool in tools_existence:
        tool_str = str(tool).replace(str(pbench_run), "")
        group_check = "default" in tool_str
        remote_check = True
        tool_check = True

        # The target tool should only have been cleared if none of the target
        # group values is empty and one of the target groups is in its path.
        if groups:
            groups_list = groups.split(",")
            group_check = all(groups_list) and any(
                x in tool_str for x in groups_list if x
            )
        # The target tool should only have been cleared if none of the target
        # remote values is empty and one of the target remote host is in its
        # path.
        if remotes:
            remotes_list = remotes.split(",")
            remote_check = all(remotes_list) and any(
                x in tool_str for x in remotes_list if x
            )
        # The target tool should only have been cleared if none of the target
        # tool values is empty and one of the target tool name is in its path.
        if tools:
            tools_list = tools.split(",")
            tool_check = all(tools_list) and any(x in tool_str for x in tools_list if x)

        if tool_check and remote_check and group_check:
            assert not tool.exists()
            # Default group should exist even if all the remotes are gone
            if "default" in tool_str:
                assert tool.parent.parent.exists()
            # if custom group exists then we need to make sure at least one
            # of the remote is not empty
            elif tool.parent.parent.exists():
                for remote_dir in tool.parent.parent.iterdir():
                    assert any(
                        remote_dir.iterdir()
                    ), f'Found an empty "remote" directory, "{remote_dir!s}", which should have been deleted.'
        else:
            assert tool.exists()


@pytest.mark.parametrize(
    "groups",
    ["", "default,wrong_group", ",default,,wrong_group,", "group1,wrong_group"],
)
@pytest.mark.parametrize(
    "remotes",
    [
        "",
        "remote1,wrong_remote1",
        ",remote1,,wrong_remote1,",
        "wrong_remote1,wrong_remote2",
    ],
)
@pytest.mark.parametrize(
    "tools",
    ["", "pidstat,wrong_tool1", ",pidstat,,wrong_tool1,", "wrong_tool1,wrong_tool2"],
)
def test_clear_tools_test86(tools_configuration, groups, remotes, tools):
    """ Attempt to clear tools at various group-remote-tool locations where the
    combination may not present on the hosts"""
    _, tools_tree = tools_configuration
    command = ["pbench-clear-tools"]
    if groups:
        command.append(f"--groups={groups}")
    if remotes:
        command.append(
            f"--remotes={','.join(map(lambda x: f'{x}.example.com' if x else x, remotes.split(',')))}"
        )
    if tools:
        command.append(f"--name={tools}")

    out, err, exitcode = pytest.helpers.capture(command)
    assert b"" == out

    empty_group_err_msg = (
        "Error: Invalid value for '-g' / '--group' / '--groups': "
        "Blank group name specified.\n"
    )
    empty_remote_err_msg = (
        "Error: Invalid value for '-r' / '--remote' / '--remotes': "
        "Blank remote name specified.\n"
    )
    empty_tool_err_msg = (
        "Error: Invalid value for '-n' / '--name' / '--names': "
        "Blank tool name specified.\n"
    )

    if not groups:
        groups = "default"

    groups_list = groups.split(",")
    remotes_list = remotes.split(",")
    tools_list = tools.split(",")

    # Check for the blank group name
    if not all(groups_list):
        assert empty_group_err_msg.encode() in err
    # Check for the blank remote host name
    elif remotes and not all(remotes_list):
        assert empty_remote_err_msg.encode() in err
    # Check for the blank tool name
    elif tools and not all(tools_list):
        assert empty_tool_err_msg.encode() in err
    else:
        # If none of the options have any blank value specified
        for group in groups_list:
            invalid_group_err_msg = (
                f'pbench-clear-tools: invalid --group option "{group}"'
            )
            if group not in tools_tree.keys():
                assert invalid_group_err_msg.encode() in err
            else:
                assert invalid_group_err_msg.encode() not in err
                if not remotes:
                    remotes_list = tools_tree[group].keys()
                for remote in remotes_list:
                    invalid_remote_err_msg = f'No remote host "{remote}.example.com"'
                    if remote not in tools_tree[group]:
                        assert invalid_remote_err_msg.encode() in err
                    else:
                        assert invalid_remote_err_msg.encode() not in err
                        wrong_tools = []
                        all_tools_removed = f'All tools removed from group "{group}" on host "{remote}.example.com"'
                        if not tools:
                            assert all_tools_removed.encode() in err
                        else:
                            for tool in tools_list:
                                if tool not in tools_tree[group][remote]:
                                    wrong_tools.append(tool)
                            if wrong_tools:
                                wrong_tools = sorted(wrong_tools)
                                wrong_tools_err_msg = (
                                    f"Tools {wrong_tools} not found in remote"
                                )
                                assert wrong_tools_err_msg.encode() in err
                            else:
                                assert all_tools_removed.encode() in err
