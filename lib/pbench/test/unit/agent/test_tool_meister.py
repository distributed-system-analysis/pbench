"""
Tests for the Tool Data Meister modules.
"""
import pathlib
import tarfile
import pytest

from pbench.agent.tool_meister import ToolMeister, get_logger


@pytest.fixture()
def get_params():
    a = {
        "benchmark_run_dir": "",
        "channel_prefix": "",
        "tds_hostname": "test.hostname.com",
        "tds_port": 4242,
        "controller": "test.hostname.com",
        "group": "",
        "hostname": "test.hostname.com",
        "label": None,
        "tool_metadata": {"persistent": {}, "transient": {}},
        "tools": [],
    }
    return a


def test_create_tar(agent_setup, get_params):
    """Test create tar file"""
    tm = ToolMeister(
        pbench_install_dir=None,
        tmp_dir=None,
        tar_path="/usr/bin/tar",
        sysinfo_dump=None,
        params=get_params,
        redis_server=None,
        logger=None,
    )
    tmp_dir = agent_setup["tmp"]

    # create a file in tmp directory
    (tmp_dir / "file1").write_text("")

    target_dir = tmp_dir.name
    parent_dir = tmp_dir.parent
    tar_file = parent_dir / f"{target_dir}.tar.xz"

    cp = tm._create_tar(tmp_dir, tar_file)
    assert cp.returncode == 0
    assert cp.stdout == b""
    tar_file.unlink()


def test_create_tar_ignore_warnings(agent_setup, get_params):
    """Test if we can suppress the errors raised during the tar creation"""
    logger = get_logger("__logger__")
    tm = ToolMeister(
        pbench_install_dir=None,
        tmp_dir=None,
        tar_path="/usr/bin/tar",
        sysinfo_dump=None,
        params=get_params,
        redis_server=None,
        logger=logger,
    )
    tmp_dir = agent_setup["tmp"]

    # create a file in tmp directory
    (tmp_dir / "file1").write_text("")

    target_dir = tmp_dir.name
    tar_file = tmp_dir / f"{target_dir}.tar.xz"

    cp = tm._create_tar(tmp_dir, tar_file)
    assert cp.returncode == 1
    assert b"file changed as we read it" in cp.stdout

    cp = tm._create_tar(tmp_dir, tar_file, retry=True)
    assert cp.returncode == 0
    assert cp.stdout == b""
    tar_file.unlink()


def test_create_empty_tar(agent_setup, get_params):
    """Test empty tar creation"""
    logger = get_logger("__logger__")
    tm = ToolMeister(
        pbench_install_dir=None,
        tmp_dir=None,
        tar_path="/usr/bin/tar",
        sysinfo_dump=None,
        params=get_params,
        redis_server=None,
        logger=logger,
    )
    tmp_dir = agent_setup["tmp"]

    # create a file in tmp directory
    (tmp_dir / "file1").write_text("")

    target_dir = tmp_dir.name
    tar_file = tmp_dir / f"{target_dir}.tar.xz"

    cp = tm._create_tar(pathlib.Path("/dev/null"), tar_file)
    assert cp.returncode == 0
    assert cp.stdout == b""

    tar = tarfile.open(tar_file)
    # There should be only one member inside this tar file i.e. null
    for member in tar.getmembers():
        assert member.name == "null"

    tar_file.unlink()
