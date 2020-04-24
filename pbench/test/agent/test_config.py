import pytest

from pbench.agent.config import AgentConfig
from pbench.common import exceptions
from pbench.test.conftest import (
    pbench_agent_config,
    stub_agent_root_dir
)

DEFAULT_CONFIG = """
[pbench-agent]
run_dir = /tmp
[results]
user = pbench
"""

def test_invalid_config(tmpdir, monkeypatch):
    config = """
    [pbench-agent]
    run_dir = /tmp
    """
    pbench_config = pbench_agent_config(tmpdir, config)
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG",str(pbench_config))
    with pytest.raises(exceptions.BadConfig):
        AgentConfig()
    
def test_valid_config(tmpdir, monkeypatch):
    pbench_config = pbench_agent_config(tmpdir, DEFAULT_CONFIG)
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG",str(pbench_config))
    config = AgentConfig()
    assert "pbench-agent" in config.pbench_config
    assert "results" in config.pbench_config

def test_get_agent(tmpdir, monkeypatch):
    pbench_config = pbench_agent_config(tmpdir, DEFAULT_CONFIG)
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG",str(pbench_config))
    assert "/tmp" in AgentConfig().get_agent()["run_dir"]

def test_get_results(tmpdir, monkeypatch):
    pbench_config = pbench_agent_config(tmpdir, DEFAULT_CONFIG)
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG",str(pbench_config))
    assert "pbench" in AgentConfig().get_results()["user"]

