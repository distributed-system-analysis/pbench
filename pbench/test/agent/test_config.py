import pytest

from pbench.agent.config import AgentConfig
from pbench.common import exceptions
from pbench.test.conftest import pbench_agent_config

DEFAULT_CONFIG = """
[pbench-agent]
run_dir = /tmp
[results]
user = pbench
"""


def test_invalid_config(tmpdir):
    config = """
    [pbench-agent]
    run_dir = /tmp
    """
    pbench_config = pbench_agent_config(tmpdir, config)
    with pytest.raises(exceptions.BadConfig):
        AgentConfig(str(pbench_config))


def test_valid_config(tmpdir):
    pbench_config = pbench_agent_config(tmpdir, DEFAULT_CONFIG)
    config = AgentConfig(str(pbench_config))
    assert "pbench-agent" in config.pbench_config
    assert "results" in config.pbench_config


def test_get_agent(tmpdir):
    pbench_config = pbench_agent_config(tmpdir, DEFAULT_CONFIG)
    assert "/tmp" in AgentConfig(str(pbench_config)).get_agent()["run_dir"]


def test_get_results(tmpdir):
    pbench_config = pbench_agent_config(tmpdir, DEFAULT_CONFIG)
    assert "pbench" in AgentConfig(str(pbench_config)).get_results()["user"]
