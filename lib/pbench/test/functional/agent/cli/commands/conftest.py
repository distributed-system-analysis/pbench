import configparser
import shutil

import pytest


@pytest.fixture
def opt_pbench(tmp_path):
    opt_pbench = tmp_path / "opt" / "pbench-agent"
    opt_pbench.mkdir(parents=True, exist_ok=True)

    yield opt_pbench


@pytest.fixture
def pbench_cfg(tmp_path, opt_pbench):
    pbench_cfg = opt_pbench / "config"
    pbench_cfg.mkdir(parents=True, exist_ok=True)
    pbench_cfg = pbench_cfg / "pbench-agent.cfg"

    yield pbench_cfg


@pytest.fixture
def agent_config(monkeypatch, tmp_path, opt_pbench, pbench_cfg, pbench_run):
    shutil.copyfile("./agent/config/pbench-agent-default.cfg", pbench_cfg)

    config = configparser.ConfigParser()
    config.read(pbench_cfg)
    config["pbench-agent"]["install-dir"] = str(opt_pbench)
    config["pbench-agent"]["pbench_run"] = str(pbench_run)
    with open(pbench_cfg, "w") as f:
        config.write(f)
    monkeypatch.setenv("_PBENCH_AGENT_CONFIG", str(pbench_cfg))
