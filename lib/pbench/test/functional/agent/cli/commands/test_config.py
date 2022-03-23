import os
import pytest


def test_pbench_run(monkeypatch, agent_config, pbench_run):
    """Use pbench_run value from pbench-agent.cfg file"""
    assert os.environ.get("pbench_run") is None
    command = ["pbench-list-tools"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0


def test_pbench_run_dir_existence(monkeypatch, agent_config, pbench_run):
    """Verify that pbench_list_tools fail when pbench_run is defined
    to a directory that doesn't exist"""
    my_pbench_run = f"{pbench_run}/test"
    monkeypatch.setenv("pbench_run", my_pbench_run)
    command = ["pbench-list-tools"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 1
    assert b"" == out
    assert (
        f"[ERROR] the provided pbench run directory, {my_pbench_run}, does not exist\n".encode()
        == err
    )


def test_pbench_dir_existence(monkeypatch, pbench_run, agent_config):
    """Verify the existence of existing pbench_run directory
    and successful completion of command"""
    pbench_run_d = pbench_run / "test_dir"
    pbench_run_d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("pbench_run", str(pbench_run_d))
    p = pbench_run_d / "tools-v1-default" / "th1.example.com"
    p.mkdir(parents=True)
    tool = p / "iostat"
    tool.write_text("--interval=30")
    tool = p / "mpstat"
    tool.write_text("--interval=300")
    command = ["pbench-list-tools"]
    out, err, exitcode = pytest.helpers.capture(command)
    assert exitcode == 0
    assert b"group: default; host: th1.example.com; tools: iostat, mpstat\n" in out
    assert b"" == err
