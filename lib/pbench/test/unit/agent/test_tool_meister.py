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


@pytest.fixture
def tool_meister():
    return ToolMeister(
        pbench_install_dir=None,
        tmp_dir=None,
        tar_path="tar_path",
        sysinfo_dump=None,
        params=tm_params,
        redis_server=None,
        logger=logging.getLogger(),
    )


class TestCreateTar:
    """Test the ToolMeister._create_tar() method behaviors."""

    @staticmethod
    def test_create_tar(tool_meister, monkeypatch):
        """Test create tar file"""

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

        cp = tool_meister._create_tar(tmp_dir, pathlib.Path(tar_file))
        assert cp.returncode == 0
        assert cp.stdout == b""

    @staticmethod
    def test_create_tar_ignore_warnings(tool_meister, monkeypatch):
        """Test creating tar with warning=none option specified"""

        def fake_run(*args, **kwargs):
            if "--warning=none" in args[0]:
                return subprocess.CompletedProcess(
                    args,
                    returncode=0,
                    stdout=b"No error after --warning=none",
                    stderr=None,
                )
            else:
                return subprocess.CompletedProcess(
                    args, returncode=1, stdout=b"Some error running tar", stderr=None
                )

        monkeypatch.setattr(subprocess, "run", fake_run)

        cp = tool_meister._create_tar(tmp_dir, pathlib.Path(tar_file))
        assert cp.returncode == 0
        assert cp.stdout == b"No error after --warning=none"

    @staticmethod
    def test_create_tar_failure(tool_meister, monkeypatch, caplog):
        """Test tar creation failure"""

        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args,
                returncode=1,
                stdout=b"Some error running tar command, empty tar creation failed",
                stderr=None,
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        cp = tool_meister._create_tar(tmp_dir, pathlib.Path(tar_file))
        assert cp.returncode == 1
        assert cp.stdout == b"Some error running tar command, empty tar creation failed"
        assert (
            "Tarball creation failed with 1 (stdout 'Some error running tar"
            f" command, empty tar creation failed') on {tmp_dir}: Re-trying now"
            in caplog.text
        )


class TestSendDirectory:
    """Test ToolMeister._send_directory()'s use of ._create_tar()"""

    # Record all the mock functions called by a test
    functions_called = []

    directory = tmp_dir / f"{tm_params['hostname']}"

    @staticmethod
    def fake_create_tar(returncode: int, stdout: bytes):
        def f(directory: pathlib.Path, tar_file: pathlib.Path):
            return subprocess.CompletedProcess(
                args=[], returncode=returncode, stdout=stdout, stderr=None
            )

        __class__.functions_called.append("fake_create_tar")
        return f

    @responses.activate
    def test_tar_create_success(self, tool_meister, monkeypatch):
        """This test should pass the tar creation in send directory"""

        def fake_unlink(*args):
            assert args[0] == pathlib.Path(f"{self.directory}.tar.xz")
            self.functions_called.append("fake_unlink")

        def fake_open(*args):
            assert args[0] == pathlib.Path(f"{self.directory}.tar.xz")
            self.functions_called.append("fake_open")
            return io.StringIO()

        def fake_rmtree(directory: pathlib.Path):
            assert directory == tmp_dir
            self.functions_called.append("fake_rmtree")

        def fake_md5(tar_file: pathlib.Path):
            assert tar_file == pathlib.Path(f"{self.directory}.tar.xz")
            self.functions_called.append("fake_md5")
            return 10, "random_md5"

        monkeypatch.setattr(shutil, "rmtree", fake_rmtree)
        monkeypatch.setattr("pbench.agent.tool_meister.md5sum", fake_md5)
        monkeypatch.setattr(pathlib.Path, "unlink", fake_unlink)
        monkeypatch.setattr(pathlib.Path, "open", fake_open)

        monkeypatch.setattr(tool_meister, "_create_tar", self.fake_create_tar(0, b""))

        url = (
            f"http://{tm_params['tds_hostname']}:{tm_params['tds_port']}/uri"
            f"/ctx/{tm_params['hostname']}"
        )
        responses.add(responses.PUT, url, status=HTTPStatus.OK, body="succeeded")

        failures = tool_meister._send_directory(self.directory, "uri", "ctx")
        functions_called, self.functions_called = self.functions_called, []
        assert functions_called == [
            "fake_create_tar",
            "fake_md5",
            "fake_open",
            "fake_rmtree",
            "fake_unlink",
        ]
        assert failures == 0

    def test_tar_create_failure(self, tool_meister, monkeypatch):
        """Check if the tar creation error is properly captured in send_directory"""
        monkeypatch.setattr(
            tool_meister,
            "_create_tar",
            self.fake_create_tar(1, b"Error in tarball creation"),
        )

        with pytest.raises(ToolMeisterError) as exc:
            failures = tool_meister._send_directory(self.directory, "uri", "ctx")
            assert failures == 1
        functions_called, self.functions_called = self.functions_called, []
        assert functions_called == ["fake_create_tar"]
        assert f"Failed to create an empty tar {self.directory}.tar.xz" in str(
            exc.value
        )
