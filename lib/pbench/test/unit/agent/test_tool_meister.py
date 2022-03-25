"""
Tests for the Tool Data Meister modules.
"""
import pathlib
import subprocess
import pytest

from pbench.agent.tool_meister import ToolMeister, get_logger

logger = get_logger("__logger__")


@pytest.fixture()
def mock_tar(monkeypatch):
    def fake_run(*args, **kwargs):
        def f():
            return

        f.returncode = 0
        f.stdout = b""
        return f

    monkeypatch.setattr(subprocess, "run", fake_run)


@pytest.fixture()
def mock_tar_no_warnings(monkeypatch):
    def fake_run(*args, **kwargs):
        def f():
            return

        if "--warning=none" in args[0]:
            f.returncode = 0
            f.stdout = b""
        else:
            f.returncode = 1
            f.stdout = b"Some error running tar"
        return f

    monkeypatch.setattr(subprocess, "run", fake_run)


@pytest.fixture()
def mock_tar_failure(monkeypatch):
    def fake_run(*args, **kwargs):
        def f():
            return

        f.returncode = 1
        f.stdout = b"Some error running tar"
        return f

    monkeypatch.setattr(subprocess, "run", fake_run)


class TestCreateTar:
    tm_params = {
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

    def test_create_tar(self, agent_setup, mock_tar):
        """Test create tar file"""
        tm = ToolMeister(
            pbench_install_dir=None,
            tmp_dir=None,
            tar_path="tar_path",
            sysinfo_dump=None,
            params=TestCreateTar.tm_params,
            redis_server=None,
            logger=None,
        )
        tmp_dir = agent_setup["tmp"]
        tar_file = "test.tar.xz"

        cp = tm._create_tar(tmp_dir, pathlib.Path(tar_file))
        assert cp.returncode == 0
        assert cp.stdout == b""

    def test_create_tar_ignore_warnings(self, agent_setup, mock_tar_no_warnings):
        """Test if we can suppress the errors raised during the tar creation"""
        tm = ToolMeister(
            pbench_install_dir=None,
            tmp_dir=None,
            tar_path="tar_path",
            sysinfo_dump=None,
            params=TestCreateTar.tm_params,
            redis_server=None,
            logger=logger,
        )
        tmp_dir = agent_setup["tmp"]
        tar_file = "test.tar.xz"

        cp = tm._create_tar(tmp_dir, pathlib.Path(tar_file))
        assert cp.returncode == 1
        assert cp.stdout == b"Some error running tar"

        cp = tm._create_tar(tmp_dir, pathlib.Path(tar_file), retry=True)
        assert cp.returncode == 0
        assert cp.stdout == b""

    def test_create_tar_failure(self, agent_setup, mock_tar_failure):
        """Test if we can suppress the errors raised during the tar creation"""
        tm = ToolMeister(
            pbench_install_dir=None,
            tmp_dir=None,
            tar_path="tar_path",
            sysinfo_dump=None,
            params=TestCreateTar.tm_params,
            redis_server=None,
            logger=logger,
        )
        tmp_dir = agent_setup["tmp"]
        tar_file = "test.tar.xz"

        cp = tm._create_tar(tmp_dir, pathlib.Path(tar_file))
        assert cp.returncode == 1
        assert cp.stdout == b"Some error running tar"


class TestSendDirectory:
    """Test create_tar in send directory of tool meister"""

    def test_tar_create_success(self, agent_setup, mock_tar, caplog):
        """This test should pass the tar creation in send directory"""

        tm = ToolMeister(
            pbench_install_dir=None,
            tmp_dir=None,
            tar_path="tar_path",
            sysinfo_dump=None,
            params=TestCreateTar.tm_params,
            redis_server=None,
            logger=logger,
        )
        directory = agent_setup["tmp"] / f"{TestCreateTar.tm_params['hostname']}"
        failures = tm._send_directory(directory, "", "")
        assert "Failed to create an empty tar" not in caplog.text
        assert failures == 1

    def test_tar_create_failure(self, agent_setup, mock_tar_failure, caplog):
        """Check if the tar creation error is properly captured in send_directory"""
        tm = ToolMeister(
            pbench_install_dir=None,
            tmp_dir=None,
            tar_path="tar_path",
            sysinfo_dump=None,
            params=TestCreateTar.tm_params,
            redis_server=None,
            logger=logger,
        )
        directory = agent_setup["tmp"] / f"{TestCreateTar.tm_params['hostname']}"
        failures = tm._send_directory(directory, "", "")
        assert "Failed to create an empty tar" in caplog.text
        assert failures == 1
