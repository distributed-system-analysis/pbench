import click
import os
import pytest
import shutil

from pathlib import Path

from pbench.agent import PbenchAgentConfig
from pbench.agent.base import BaseCommand
from pbench.common.exceptions import BadConfig


def test_invalid_config(setup, monkeypatch):
    shutil.copyfile(
        "./lib/pbench/test/unit/agent/config/pbench-agent.invalid.cfg",
        str(setup["cfg_dir"] / "pbench-agent.invalid.cfg"),
    )
    with pytest.raises(BadConfig):
        PbenchAgentConfig(setup["cfg_dir"] / "pbench-agent.invalid.cfg")


def test_valid_config():
    config = PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"])
    assert "pbench-agent" in config.conf
    assert "results" in config.conf


def test_agent_attr(setup):
    TMP = setup["tmp"]
    assert (
        f"{TMP}/var/lib/pbench-agent"
        == PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"]).agent["pbench_run"]
    )


def test_results_attr():
    assert (
        "pbench"
        in PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"]).results["user"]
    )


# Monkeypatching different Classes and Methods to test Pbench-run value


class MockPbenchAgentConfig:
    """Mock class for PbenchAgentConfig"""

    def __init__(self, cfg_name: str):
        self.pbench_run = "/test/pbench-run"
        self.pbench_log = "logger"
        self.pbench_install_dir = Path("/test/install_dir")
        self.ssh_opts = "/ssh_opts"
        self.scp_opts = "/scp_opts"


def mock_exist(path: Path):
    """mock method for Path.exist"""
    return True


def mock_current_context():
    """mock get_current_context from click package"""
    None


class MockContext:
    """Mocking Context"""

    config = "/test/pbench-config-path"


class TestCommand(BaseCommand):
    """Mock of class that extends BaseCommand"""

    def __init__(self):
        super(TestCommand, self).__init__(MockContext())

    def execute(self):
        pass


def test_pbench_run_path(monkeypatch):
    """Use pbench_run value from pbench-agent.cfg file"""
    assert os.environ.get("pbench_run") is None
    monkeypatch.setattr(PbenchAgentConfig, "__init__", MockPbenchAgentConfig.__init__)
    monkeypatch.setattr(Path, "exists", mock_exist)
    pbench_run_val = TestCommand().pbench_run
    assert str(pbench_run_val) == "/test/pbench-run"


def test_pbench_run_as_env(monkeypatch):
    """Use pbench_run value, passed manually through
    `pbench-run` environment variable"""
    monkeypatch.setenv("pbench_run", "/test/pbench-run/environ")
    monkeypatch.setattr(PbenchAgentConfig, "__init__", MockPbenchAgentConfig.__init__)
    monkeypatch.setattr(Path, "exists", mock_exist)
    pbench_run_val = TestCommand().pbench_run
    assert str(pbench_run_val) == "/test/pbench-run/environ"


def test_pbench_run_dir_existence(monkeypatch):
    """Verify that pbench_list_tools fail when pbench_run is defined
    to a directory that doesn't exist"""
    monkeypatch.setattr(PbenchAgentConfig, "__init__", MockPbenchAgentConfig.__init__)
    monkeypatch.setattr(click, "get_current_context", mock_current_context)
    pbench_run = TestCommand().pbench_run
    assert pbench_run
    # assert pbench_run.startswith("[ERROR] pbench run directory does not exist")
