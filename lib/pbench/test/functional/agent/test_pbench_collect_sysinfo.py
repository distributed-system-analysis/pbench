import pytest


def test_pbench_collect_sysinfo_tools_help():
    command = ["pbench-collect-sysinfo", "--help"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"--help" in out


def test_pbench_collect_sysinfo_tools_help_failed():
    command = ["pbench-collect-sysinfo", "--foo"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 2


def test_pbench_collect_sysinfo_tools_with_options(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    command = ["pbench-collect-sysinfo", "--options"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"default" in out


def test_pbench_collect_sysinfo_tools_check_all(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    command = ["pbench-collect-sysinfo", "--check", "--sysinfo", "all"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0


def test_pbench_collect_sysinfo_tools_check_none(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    command = ["pbench-collect-sysinfo", "--check", "--sysinfo", "none"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0


def test_pbench_collect_sysinfo_tools_check_default(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    command = ["pbench-collect-sysinfo", "--check", "--sysinfo", "default"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0


def test_pbench_collect_sysinfo_tools_check(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    command = [
        "pbench-collect-sysinfo",
        "--check",
        "--sysinfo",
        "block,libvirt,kernel_config,topology",
    ]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0


def test_pbench_collect_sysinfo_tools_bad(
    tmpdir, create_agent_environment, pbench_run, pbench_conf, monkeypatch
):
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", pbench_conf.strpath)
    command = [
        "pbench-collect-sysinfo",
        "--check",
        "--sysinfo",
        "block,libvirt,kernel_config,bad",
    ]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 1
    assert b"invalid sysinfo option: bad\n" in out
