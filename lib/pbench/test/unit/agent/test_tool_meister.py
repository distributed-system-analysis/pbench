"""
Tests for the Tool Meister modules.
"""
import io
import logging
import shutil
import subprocess
from http import HTTPStatus
from pathlib import Path

import pytest
import responses

from pbench.agent.tool_meister import ToolMeister, ToolMeisterError

tar_file = "test.tar.xz"
tmp_dir = Path("nonexistent/tmp/dir")
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

        def mock_run(*args, **kwargs):
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

        monkeypatch.setattr(subprocess, "run", mock_run)

        cp = tool_meister._create_tar(tmp_dir, Path(tar_file))
        assert cp.returncode == 0
        assert cp.stdout == b""

    @staticmethod
    def test_create_tar_ignore_warnings(tool_meister, monkeypatch):
        """Test creating tar with warning=none option specified"""

        expected_std_out = b"No error after --warning=none"

        def mock_run(*args, **kwargs):
            if "--warning=none" in args[0]:
                return subprocess.CompletedProcess(
                    args,
                    returncode=0,
                    stdout=expected_std_out,
                    stderr=None,
                )
            else:
                return subprocess.CompletedProcess(
                    args, returncode=1, stdout=b"Some error running tar", stderr=None
                )

        monkeypatch.setattr(subprocess, "run", mock_run)

        cp = tool_meister._create_tar(tmp_dir, Path(tar_file))
        assert cp.returncode == 0
        assert cp.stdout == expected_std_out

    @staticmethod
    def test_create_tar_failure(tool_meister, monkeypatch, caplog):
        """Test tar creation failure"""

        # Record number of times mock functions called by this test
        functions_called = []

        expected_std_out = b"Some error running tar command, empty tar creation failed"

        def mock_run(*args, **kwargs):
            functions_called.append("mock_run")
            return subprocess.CompletedProcess(
                args,
                returncode=1,
                stdout=expected_std_out,
                stderr=None,
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        cp = tool_meister._create_tar(tmp_dir, Path(tar_file))
        assert cp.returncode == 1
        assert cp.stdout == expected_std_out
        assert functions_called == ["mock_run", "mock_run"]


class TestSendDirectory:
    """Test ToolMeister._send_directory()"""

    directory = tmp_dir / f"{tm_params['hostname']}"

    @staticmethod
    def mock_create_tar(returncode: int, stdout: bytes, functions_called: list):
        def f(directory: Path, tar_file: Path):
            functions_called.append("mock_create_tar")
            return subprocess.CompletedProcess(
                args=[], returncode=returncode, stdout=stdout, stderr=None
            )

        return f

    @responses.activate
    def test_tar_create_success(self, tool_meister, monkeypatch):
        """This test should pass the tar creation in send directory"""

        # Record all the mock functions called by this test
        functions_called = []

        def mock_unlink(*args):
            assert args[0] == Path(f"{self.directory}.tar.xz")
            functions_called.append("mock_unlink")

        def mock_open(*args):
            assert args[0] == Path(f"{self.directory}.tar.xz")
            functions_called.append("mock_open")
            return io.StringIO()

        def mock_rmtree(directory: Path):
            assert directory == tmp_dir
            functions_called.append("mock_rmtree")

        def mock_md5(tar_file: Path):
            assert tar_file == Path(f"{self.directory}.tar.xz")
            functions_called.append("mock_md5")
            return 10, "random_md5"

        monkeypatch.setattr(shutil, "rmtree", mock_rmtree)
        monkeypatch.setattr("pbench.agent.tool_meister.md5sum", mock_md5)
        monkeypatch.setattr(Path, "unlink", mock_unlink)
        monkeypatch.setattr(Path, "open", mock_open)

        monkeypatch.setattr(
            tool_meister, "_create_tar", self.mock_create_tar(0, b"", functions_called)
        )

        url = (
            f"http://{tm_params['tds_hostname']}:{tm_params['tds_port']}/uri"
            f"/ctx/{tm_params['hostname']}"
        )
        responses.add(responses.PUT, url, status=HTTPStatus.OK, body="succeeded")

        failures = tool_meister._send_directory(self.directory, "uri", "ctx")
        assert functions_called == [
            "mock_create_tar",
            "mock_md5",
            "mock_open",
            "mock_rmtree",
            "mock_unlink",
        ]
        assert failures == 0

    def test_tar_create_failure(self, tool_meister, monkeypatch):
        """Check if the tar creation error is properly captured in send_directory"""

        # Record all the mock functions called by this test
        functions_called = []

        def mock_unlink(*args):
            assert args[0] == Path(f"{self.directory}.tar.xz")
            functions_called.append("mock_unlink")

        monkeypatch.setattr(Path, "unlink", mock_unlink)

        monkeypatch.setattr(
            tool_meister,
            "_create_tar",
            self.mock_create_tar(1, b"Error in tarball creation", functions_called),
        )

        with pytest.raises(ToolMeisterError) as exc:
            tool_meister._send_directory(self.directory, "uri", "ctx")

        assert functions_called == ["mock_create_tar", "mock_create_tar", "mock_unlink"]
        assert f"Failed to create an empty tar {self.directory}.tar.xz" in str(
            exc.value
        )
