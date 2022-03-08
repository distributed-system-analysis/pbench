import pytest
import shutil

from pbench.test import on_disk_config


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


def do_setup(tmp_d):
    """Perform on disk agent config setup.

    Accept a single temporary directory created by its caller, creating a
    proper pbench directory hierarchy in it, with appropriately constructed
    configuration files.

    Returns a Path object for the created pbench configuration directory.
    """
    opt_pbench = tmp_d / "opt" / "pbench-agent"
    pbench_cfg = opt_pbench / "config"
    pbench_cfg.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(
        "./agent/config/pbench-agent-default.cfg",
        str(pbench_cfg / "pbench-agent-default.cfg"),
    )

    cfg_file = pbench_cfg / "pbench-agent.cfg"
    with open(cfg_file, "w") as fp:
        fp.write(agent_cfg_tmpl.format(TMP=tmp_d))

    return pbench_cfg


@pytest.fixture(scope="session", autouse=True)
def agent_setup(tmp_path_factory):
    """Test package setup for agent unit tests"""
    return on_disk_config(tmp_path_factory, "agent", do_setup)


@pytest.fixture(autouse=True)
def setup(tmp_path_factory, agent_setup, monkeypatch):
    """Test package setup for pbench-agent"""
    var = agent_setup["tmp"] / "var" / "lib" / "pbench-agent"
    try:
        if var.exists():
            assert var.is_dir()
            shutil.rmtree(str(var))
    except Exception as exc:
        print(exc)
    var.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv(
        "_PBENCH_AGENT_CONFIG", str(agent_setup["cfg_dir"] / "pbench-agent.cfg")
    )
    return agent_setup
