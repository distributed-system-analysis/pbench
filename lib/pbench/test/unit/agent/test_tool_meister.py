"""
Tests for the Tool Meister modules.
"""
import io
import logging
import pathlib
import shutil
import subprocess
from http import HTTPStatus

import pytest
import responses

from pbench.agent.tool_meister import ToolMeister, ToolMeisterError

tar_file = "test.tar.xz"
tmp_dir = pathlib.Path("nonexistent/tmp/dir")


@pytest.fixture()
def mock_tar(monkeypatch):
    def fake_run(*args, **kwargs):
        assert kwargs["cwd"] == tmp_dir.parent
        assert kwargs["stdin"] is None
        assert kwargs["stderr"] == subprocess.STDOUT
        assert kwargs["stdout"] == subprocess.PIPE
        c = subprocess.CompletedProcess(args, returncode=0, stdout=b"", stderr=None)
        assert all(
            x in c.args[0]
            for x in [
                "tar_path",
                "--create",
                "--xz",
                "--force-local",
                f"--file={tar_file}",
            ]
        )
        return c

    monkeypatch.setattr(subprocess, "run", fake_run)


@pytest.fixture()
def mock_tar_no_warnings(monkeypatch):
    def fake_run(*args, **kwargs):
        if "--warning=none" in args[0]:
            return subprocess.CompletedProcess(
                args, returncode=0, stdout=b"No error after --warning=none", stderr=None
            )
        else:
            return subprocess.CompletedProcess(
                args, returncode=1, stdout=b"Some error running tar", stderr=None
            )

    monkeypatch.setattr(subprocess, "run", fake_run)


@pytest.fixture()
def mock_tar_failure(monkeypatch):
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args,
            returncode=1,
            stdout=b"Some error running tar command, empty tar creation failed",
            stderr=None,
        )

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

    def test_create_tar(self, mock_tar):
        """Test create tar file"""
        tm = ToolMeister(
            pbench_install_dir=None,
            tmp_dir=None,
            tar_path="tar_path",
            sysinfo_dump=None,
            params=self.tm_params,
            redis_server=None,
            logger=None,
        )
        cp = tm._create_tar(tmp_dir, pathlib.Path(tar_file))
        assert cp.returncode == 0
        assert cp.stdout == b""

    def test_create_tar_ignore_warnings(self, mock_tar_no_warnings):
        """Test creating tar with warning=none option specified"""
        tm = ToolMeister(
            pbench_install_dir=None,
            tmp_dir=None,
            tar_path="tar_path",
            sysinfo_dump=None,
            params=self.tm_params,
            redis_server=None,
            logger=logging.getLogger(),
        )

        cp = tm._create_tar(tmp_dir, pathlib.Path(tar_file))
        assert cp.returncode == 0
        assert cp.stdout == b"No error after --warning=none"

    def test_create_tar_failure(self, mock_tar_failure, caplog):
        """Test tar creation failure"""
        tm = ToolMeister(
            pbench_install_dir=None,
            tmp_dir=None,
            tar_path="tar_path",
            sysinfo_dump=None,
            params=self.tm_params,
            redis_server=None,
            logger=logging.getLogger(),
        )

        cp = tm._create_tar(tmp_dir, pathlib.Path(tar_file))
        assert cp.returncode == 1
        assert cp.stdout == b"Some error running tar command, empty tar creation failed"
        assert (
            f"Tarball creation failed with 1 (stdout 'Some error running tar command, empty tar creation failed') on {tmp_dir}: Re-trying now"
            in caplog.text
        )


class TestSendDirectory:
    """Test ToolMeister._send_directory()'s use of ._create_tar()"""

    # Record all the mock functions called by a test
    function_called = []

    directory = tmp_dir / f"{TestCreateTar.tm_params['hostname']}"

    @staticmethod
    def add_http_mock_response(
        uri: str, code: HTTPStatus = HTTPStatus.OK, text: str = "succeeded"
    ):
        responses.add(responses.PUT, uri, status=code, body=text)

    @staticmethod
    def fake_tar(returncode: int, stdout: bytes):
        def f(directory: pathlib.Path, tar_file: pathlib.Path):
            return subprocess.CompletedProcess(
                args=[], returncode=returncode, stdout=stdout, stderr=None
            )

        TestSendDirectory.function_called.append("fake_tar")
        return f

    @staticmethod
    def fake_unlink(*args):
        assert args[0] == pathlib.Path(f"{TestSendDirectory.directory}.tar.xz")
        TestSendDirectory.function_called.append("fake_unlink")
        pass

    @staticmethod
    def fake_open(*args):
        assert args[0] == pathlib.Path(f"{TestSendDirectory.directory}.tar.xz")
        TestSendDirectory.function_called.append("fake_open")
        return io.StringIO()

    def fake_rmtree(self, directory: pathlib.Path):
        assert directory == tmp_dir
        self.function_called.append("fake_rmtree")
        pass

    def fake_md5(self, tar_file: pathlib.Path):
        assert tar_file == pathlib.Path(f"{self.directory}.tar.xz")
        self.function_called.append("fake_md5")
        return 10, "random_md5"

    @responses.activate
    def test_tar_create_success(self, monkeypatch):
        """This test should pass the tar creation in send directory"""

        monkeypatch.setattr(shutil, "rmtree", self.fake_rmtree)
        monkeypatch.setattr("pbench.agent.tool_meister.md5sum", self.fake_md5)
        monkeypatch.setattr(pathlib.Path, "unlink", self.fake_unlink)
        monkeypatch.setattr(pathlib.Path, "open", self.fake_open)

        tm = ToolMeister(
            pbench_install_dir=None,
            tmp_dir=None,
            tar_path="tar_path",
            sysinfo_dump=None,
            params=TestCreateTar.tm_params,
            redis_server=None,
            logger=logging.getLogger(),
        )

        monkeypatch.setattr(tm, "_create_tar", self.fake_tar(0, b""))

        url = (
            f"http://{TestCreateTar.tm_params['tds_hostname']}:{TestCreateTar.tm_params['tds_port']}/uri"
            f"/ctx/{TestCreateTar.tm_params['hostname']}"
        )
        self.add_http_mock_response(url)

        failures = tm._send_directory(self.directory, "uri", "ctx")
        assert self.function_called == [
            "fake_tar",
            "fake_md5",
            "fake_open",
            "fake_rmtree",
            "fake_unlink",
        ]
        assert failures == 0

    def test_tar_create_failure(self, mock_tar_failure, monkeypatch):
        """Check if the tar creation error is properly captured in send_directory"""
        tm = ToolMeister(
            pbench_install_dir=None,
            tmp_dir=None,
            tar_path="tar_path",
            sysinfo_dump=None,
            params=TestCreateTar.tm_params,
            redis_server=None,
            logger=logging.getLogger(),
        )

        monkeypatch.setattr(
            tm, "_create_tar", self.fake_tar(1, b"Error in tarball creation")
        )

        with pytest.raises(ToolMeisterError) as exc:
            failures = tm._send_directory(self.directory, "uri", "ctx")
            assert failures == 1
        assert f"Failed to create an empty tar {self.directory}.tar.xz" in str(
            exc.value
        )
