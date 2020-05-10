import pytest

from pbench.lib.agent import config as cfg
from pbench.lib.agent import exceptions
from pbench.test.agent.conftest import pbench_agent_config

DEFAULT_CONFIG = """
[pbench-agent]
install-dir = /opt/pbench-agent
pbench_user = pbench
pbench_group = pbench
pbench_run = /var/lib/pbench-agent

[results]
user = pbench
"""


def test_invalid_config(tmpdir):
    config = ""
    pbench_config = pbench_agent_config(tmpdir, config)
    with pytest.raises(exceptions.BadConfig):
        cfg.AgentConfig(str(pbench_config))


def test_valid_config(tmpdir):
    pbench_config = pbench_agent_config(tmpdir, DEFAULT_CONFIG)
    config = cfg.AgentConfig(str(pbench_config))
    assert "pbench-agent" in config.pbench_config
    assert "results" in config.pbench_config


def test_get_agent(tmpdir):
    pbench_config = pbench_agent_config(tmpdir, DEFAULT_CONFIG)
    assert (
        "/var/lib/pbench-agent"
        in cfg.AgentConfig(str(pbench_config)).get_agent()["pbench_run"]
    )


def test_get_results(tmpdir):
    pbench_config = pbench_agent_config(tmpdir, DEFAULT_CONFIG)
    assert "pbench" in cfg.AgentConfig(str(pbench_config)).get_results()["user"]


def test_get_results_missing(tmpdir):
    PBENCH_CONFIG = """
    [pbench-agent]
    run_dir = /tmp
    """
    pbench_config = pbench_agent_config(tmpdir, PBENCH_CONFIG)
    assert {} == cfg.AgentConfig(str(pbench_config)).get_results()


def test_pbench_rundir(tmpdir):
    pbench_config = pbench_agent_config(tmpdir, DEFAULT_CONFIG)
    assert "/var/lib/pbench-agent" == cfg.AgentConfig(str(pbench_config)).rundir


def test_pbench_installdir(tmpdir):
    pbench_config = pbench_agent_config(tmpdir, DEFAULT_CONFIG)
    assert "/opt/pbench-agent" == cfg.AgentConfig(str(pbench_config)).installdir


def test_pbench_logdir(tmpdir):
    pbench_config = pbench_agent_config(tmpdir, DEFAULT_CONFIG)
    assert None is cfg.AgentConfig(str(pbench_config)).logdir
