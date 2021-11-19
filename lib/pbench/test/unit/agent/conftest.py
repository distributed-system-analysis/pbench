import json
import pytest
import shutil

from filelock import FileLock
from pathlib import Path


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


def do_setup(tmp_path_factory):
    """Perform on disk agent config setup."""
    # Create a single temporary directory for the "/opt/pbench-agent" and
    # "/var/lib/pbench-agent" directories.
    tmp_d = tmp_path_factory.mktemp("agent-tmp")

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

    return dict(tmp=tmp_d, cfg_dir=pbench_cfg)


def on_disk_agent_config(tmp_path_factory):
    """Base setup function shared between the agent and functional tests.

    See https://github.com/pytest-dev/pytest-xdist.
    """
    root_tmp_dir = tmp_path_factory.getbasetemp()
    marker = root_tmp_dir / "agent-marker.json"
    with FileLock(f"{marker}.lock"):
        if marker.is_file():
            the_setup = json.loads(marker.read_text())
            the_setup["tmp"] = Path(the_setup["tmp"])
            the_setup["cfg_dir"] = Path(the_setup["cfg_dir"])
        else:
            the_setup = do_setup(tmp_path_factory)
            data = dict(tmp=str(the_setup["tmp"]), cfg_dir=str(the_setup["cfg_dir"]))
            marker.write_text(json.dumps(data))
    return the_setup


@pytest.fixture(scope="session", autouse=True)
def agent_setup(tmp_path_factory):
    """Test package setup for agent unit tests"""
    on_disk_agent_config(tmp_path_factory)


@pytest.fixture(autouse=True)
def setup(tmp_path_factory, monkeypatch):
    """Test package setup for pbench-agent"""
    _setup = on_disk_agent_config(tmp_path_factory)
    var = _setup["tmp"] / "var" / "lib" / "pbench-agent"
    try:
        if var.exists():
            assert var.is_dir()
            shutil.rmtree(str(var))
    except Exception as exc:
        print(exc)
    var.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv(
        "_PBENCH_AGENT_CONFIG", str(_setup["cfg_dir"] / "pbench-agent.cfg")
    )
    return _setup
