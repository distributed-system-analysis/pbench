import os
import pytest

from pbench.agent import PbenchAgentConfig
from pbench.common.exceptions import BadConfig


def test_invalid_config(invalid_config):
    with pytest.raises(BadConfig):
        PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"])


def test_valid_config(valid_config):
    config = PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"])
    assert "pbench-agent" in config.conf
    assert "results" in config.conf


def test_agent_attr(valid_config, pytestconfig):
    TMP = pytestconfig.cache.get("TMP", None)
    assert (
        f"{TMP}/var/lib/pbench-agent"
        == PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"]).agent["pbench_run"]
    )


def test_results_attr(valid_config):
    assert (
        "pbench"
        in PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"]).results["user"]
    )
