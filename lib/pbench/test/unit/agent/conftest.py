import shutil
import tempfile
import pytest

from pathlib import Path


def base_setup(request, pytestconfig):
    """Test package setup for pbench-agent"""
    print("Test SETUP for pbench-agent")

    # Create a single temporary directory for the "/opt/pbench-agent" and
    # "/var/lib/pbench-agent" directories.
    TMP = tempfile.TemporaryDirectory(suffix=".d", prefix="pbench-agent-unit-tests.")
    tmp_d = Path(TMP.name)

    opt_pbench = tmp_d / "opt" / "pbench-agent"
    pbench_cfg = opt_pbench / "config"
    pbench_cfg.mkdir(parents=True, exist_ok=True)

    var = tmp_d / "var" / "lib" / "pbench_agent"
    var.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(
        "./agent/config/pbench-agent-default.cfg",
        str(pbench_cfg / "pbench-agent-default.cfg"),
    )

    pytestconfig.cache.set("TMP", TMP.name)
    cfg_file = pbench_cfg / "pbench-agent.cfg"
    pytestconfig.cache.set("_PBENCH_AGENT_CONFIG", str(cfg_file))

    def teardown():
        """Test package teardown for pbench-agent"""
        print("Test TEARDOWN for pbench-agent")
        TMP.cleanup()

    request.addfinalizer(teardown)


@pytest.fixture(scope="session", autouse=True)
def setup(request, pytestconfig):
    return base_setup(request, pytestconfig)


agent_cfg_tmpl = """[DEFAULT]
pbench_install_dir = {TMP}/opt/pbench-agent
pbench_results_redirector = pbench.results.example.com

[pbench-agent]
debug_unittest = 1
pbench_run = {TMP}/var/lib/pbench-agent

[config]
path = %(pbench_install_dir)s/config
files = pbench-agent-default.cfg
"""


@pytest.fixture
def valid_config(pytestconfig):
    TMP = pytestconfig.cache.get("TMP", None)
    cfg_file = pytestconfig.cache.get("_PBENCH_AGENT_CONFIG", None)
    with open(cfg_file, "w") as fp:
        fp.write(agent_cfg_tmpl.format(TMP=TMP))


@pytest.fixture
def invalid_config(pytestconfig):
    cfg_file = pytestconfig.cache.get("_PBENCH_AGENT_CONFIG", None)
    shutil.copyfile("./lib/pbench/test/unit/config/pbench-agent.invalid.cfg", cfg_file)


@pytest.fixture(autouse=True)
def agent_config_env(pytestconfig, monkeypatch):
    cfg_file = pytestconfig.cache.get("_PBENCH_AGENT_CONFIG", None)
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", cfg_file)
