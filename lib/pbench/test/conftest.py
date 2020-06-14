import configparser
import getpass
import os
import shutil

import pytest


@pytest.fixture
def pbench_run(tmpdir):
    pbench_run = tmpdir / "test/var/lib/pbench-agent"
    os.makedirs(pbench_run)
    yield pbench_run


@pytest.fixture
def pbench_installdir(tmpdir):
    pbench_installdir = tmpdir / "test/opt/pbench-agent"
    os.makedirs(pbench_installdir)
    yield pbench_installdir


@pytest.fixture
def pbench_conf(tmpdir):
    pbench_config = tmpdir / "pbench-agent.cfg"
    yield pbench_config


@pytest.fixture
def pbench_logdir(tmpdir):
    pbench_logdir = tmpdir / "test/var/lib/pbench-agent/pbench.log"
    pbench_logdir.write("")
    yield pbench_logdir


@pytest.fixture
def create_agent_environment(pbench_run, pbench_installdir, pbench_conf, tmpdir):

    agent_config = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "config/pbench-agent-default.cfg"
    )
    conf = configparser.ConfigParser()
    conf.read(agent_config)
    conf.add_section("results")
    conf.set("results", "user", "pbench")
    conf.add_section("pbench-agent")
    conf.set("pbench-agent", "install-dir", pbench_installdir.strpath)
    conf.set("pbench-agent", "pbench_run", pbench_installdir.strpath)
    conf.set("pbench-agent", "pbench_user", getpass.getuser())
    conf.set("pbench-agent", "pbench_group", getpass.getuser())
    conf.set("pbench-agent", "pbench_run", pbench_run.strpath)
    conf.set("pbench-agent", "pbench_log", "%s/pbench.log" % pbench_run.strpath)

    conf.write(open(pbench_conf, "w"))


@pytest.fixture
def install_tool_scripts(pbench_installdir):
    tool_scripts = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "../../../agent/tool-scripts"
    )
    tool_dir = pbench_installdir / "tool-scripts"
    shutil.copytree(tool_scripts, tool_dir)


@pytest.fixture
def pbench_config(pbench_conf):
    conf = configparser.ConfigParser()
    conf.read(pbench_conf)
    yield conf


@pytest.helpers.register
def get_pbench_config(f):
    c = configparser.ConfigParser()
    c.read(f)
    return c
