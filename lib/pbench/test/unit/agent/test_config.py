import os
import pytest
import shutil

from pbench.agent import PbenchAgentConfig
from pbench.common.exceptions import BadConfig


def test_invalid_config(setup, monkeypatch):
    shutil.copyfile(
        "./lib/pbench/test/unit/agent/config/pbench-agent.invalid.cfg",
        str(setup["cfg_dir"] / "pbench-agent.invalid.cfg"),
    )
    monkeypatch.setenv(
        "_PBENCH_AGENT_CONFIG", str(setup["cfg_dir"] / "pbench-agent.invalid.cfg")
    )
    with pytest.raises(BadConfig):
        PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"])


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
