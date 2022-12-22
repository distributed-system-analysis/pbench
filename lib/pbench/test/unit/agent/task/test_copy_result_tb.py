from http import HTTPStatus
import io
import os
from pathlib import Path
from typing import Callable

import pytest
import requests
import responses

from pbench.agent import PbenchAgentConfig
from pbench.agent.results import CopyResultTb


class TestCopyResults:
    @pytest.fixture(autouse=True)
    def config(self):
        # Setup the configuration
        self.config = PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"])
        yield
        # Teardown the setup
        self.config = None

    @staticmethod
    def get_path_exists_mock(path: str, result: bool) -> Callable:
        def mock_func(self: Path) -> bool:
            assert self.name == path
            return result

        return mock_func

    @staticmethod
    def get_path_open_mock(path: str, result: io.IOBase) -> Callable:
        def mock_func(self: Path, mode: str) -> io.IOBase:
            assert self.name == path
            return result

        return mock_func

    def test_controller_invalid(self, agent_logger):
        """Test error when the controller value is invalid"""
        bad_controller_name = "#invalid!"
        expected_error_message = (
            f"Controller {bad_controller_name!r} is not a valid host name"
        )
        with pytest.raises(ValueError) as excinfo:
            CopyResultTb(
                bad_controller_name,
                "tarball",
                0,
                "ignoremd5",
                self.config,
                agent_logger,
            )
        assert str(excinfo.value).endswith(
            expected_error_message
        ), f"expected='...{expected_error_message}', found='{str(excinfo.value)}'"

    def test_tarball_nonexistent(self, monkeypatch, agent_logger):
        """Test error when the tarball file does not exist"""
        bad_tarball_name = "nonexistent-tarball.tar.xz"
        expected_error_message = f"Tar ball '{bad_tarball_name}' does not exist"

        monkeypatch.setattr(
            Path, "exists", self.get_path_exists_mock(bad_tarball_name, False)
        )

        with pytest.raises(FileNotFoundError) as excinfo:
            CopyResultTb(
                "controller",
                bad_tarball_name,
                0,
                "ignoremd5",
                self.config,
                agent_logger,
            )
        assert str(excinfo.value).endswith(
            expected_error_message
        ), f"expected='...{expected_error_message}', found='{str(excinfo.value)}'"

    @responses.activate
    @pytest.mark.parametrize("access", ("public", "private", None))
    def test_with_access(self, access: str, monkeypatch, agent_logger):
        tb_name = "test_tarball.tar.xz"
        tb_contents = "I'm a result!"

        def request_callback(request: requests.Request):
            if access is None:
                assert "access" not in request.params
            else:
                assert "access" in request.params
                assert request.params["access"] == access
            return HTTPStatus.OK, {}, ""

        responses.add_callback(
            responses.PUT,
            f"{self.config.get('results', 'server_rest_url')}/upload/{tb_name}",
            callback=request_callback,
        )

        monkeypatch.setattr(Path, "exists", self.get_path_exists_mock(tb_name, True))
        monkeypatch.setattr(
            Path, "open", self.get_path_open_mock(tb_name, io.StringIO(tb_contents))
        )

        crt = CopyResultTb(
            "controller",
            tb_name,
            len(tb_contents),
            "someMD5",
            self.config,
            agent_logger,
        )
        if access is None:
            crt.copy_result_tb("token")
        else:
            crt.copy_result_tb("token", access)
        # If we got this far without an exception, then the test passes.

    @responses.activate
    def test_connection_error(self, monkeypatch, agent_logger):
        tb_name = "test_tarball.tar.xz"
        tb_contents = "I'm a result!"
        upload_url = f"{self.config.get('results', 'server_rest_url')}/upload/{tb_name}"
        expected_error_message = f"Cannot connect to '{upload_url}'"
        responses.add(
            responses.PUT, upload_url, body=requests.exceptions.ConnectionError("uh-oh")
        )

        monkeypatch.setattr(Path, "exists", self.get_path_exists_mock(tb_name, True))
        monkeypatch.setattr(
            Path, "open", self.get_path_open_mock(tb_name, io.StringIO(tb_contents))
        )

        with pytest.raises(RuntimeError) as excinfo:
            crt = CopyResultTb(
                "controller",
                tb_name,
                len(tb_contents),
                "someMD5",
                self.config,
                agent_logger,
            )
            crt.copy_result_tb("token")
        assert str(excinfo.value).endswith(
            expected_error_message
        ), f"expected='...{expected_error_message}', found='{str(excinfo.value)}'"

    @responses.activate
    def test_unexpected_error(self, monkeypatch, agent_logger):
        tb_name = "test_tarball.tar.xz"
        tb_contents = "I'm a result!"
        upload_url = f"{self.config.get('results', 'server_rest_url')}/upload/{tb_name}"

        responses.add(responses.PUT, upload_url, body=RuntimeError("uh-oh"))

        monkeypatch.setattr(Path, "exists", self.get_path_exists_mock(tb_name, True))
        monkeypatch.setattr(
            Path, "open", self.get_path_open_mock(tb_name, io.StringIO(tb_contents))
        )

        with pytest.raises(CopyResultTb.FileUploadError) as excinfo:
            crt = CopyResultTb(
                "controller",
                tb_name,
                len(tb_contents),
                "someMD5",
                self.config,
                agent_logger,
            )
            crt.copy_result_tb("token")
        assert "something wrong" in str(excinfo.value)
