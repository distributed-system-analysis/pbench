import hashlib
from http import HTTPStatus
import io
import json
import os
from pathlib import Path
from typing import Callable

import pytest
import requests
import responses

from pbench.agent import PbenchAgentConfig
from pbench.agent.results import CopyResult, CopyResultToRelay, CopyResultToServer


class TestCopyResults:
    @pytest.fixture(autouse=True)
    def config(self):
        # Setup the configuration
        TestCopyResults.config = PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"])
        yield
        # Teardown the setup
        TestCopyResults.config = None

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

    def test_tarball_nonexistent(self, monkeypatch, agent_logger):
        """Test error when the tarball file does not exist"""
        bad_tarball_name = "nonexistent-tarball.tar.xz"
        expected_error_message = f"Tar ball '{bad_tarball_name}' does not exist"

        with monkeypatch.context() as m:
            m.setattr(
                Path, "exists", self.get_path_exists_mock(bad_tarball_name, False)
            )

            with pytest.raises(FileNotFoundError) as excinfo:
                CopyResultToServer(
                    self.config,
                    agent_logger,
                    "http://example.com",
                    "token",
                    "private",
                    None,
                ).push(Path(bad_tarball_name), "ignoremd5")

        assert str(excinfo.value).endswith(
            expected_error_message
        ), f"expected='...{expected_error_message}', found='{str(excinfo.value)}'"

    @responses.activate
    @pytest.mark.parametrize("server", (None, "http://test.foo.example.com"))
    @pytest.mark.parametrize("access", ("public", "private", None))
    def test_with_access(self, monkeypatch, agent_logger, server: str, access: str):
        tb_name = "test_tarball.tar.xz"
        tb_contents = b"I'm a result!"

        def request_callback(request: requests.Request):
            if access is None:
                assert "access" not in request.params
            else:
                assert "access" in request.params
                assert request.params["access"] == access
            return HTTPStatus.CREATED, {}, ""

        api = self.config.get("results", "rest_endpoint")
        rest_uri = self.config.get("results", "server_rest_url")
        mock_uri = f"{server}/{api}" if server else rest_uri
        responses.add_callback(
            responses.PUT, f"{mock_uri}/upload/{tb_name}", callback=request_callback
        )

        with monkeypatch.context() as m:
            m.setattr(Path, "exists", self.get_path_exists_mock(tb_name, True))
            m.setattr(
                Path, "open", self.get_path_open_mock(tb_name, io.BytesIO(tb_contents))
            )

            res = CopyResultToServer(
                self.config, agent_logger, server, None, access, None
            ).push(Path(tb_name), "someMD5")

        assert res.status_code == HTTPStatus.CREATED

    @responses.activate
    @pytest.mark.parametrize(
        "metadata", (["pbench.test:TEST", "pbench.sat:FOO"], (), None)
    )
    def test_with_metadata(self, metadata, monkeypatch, agent_logger):
        tb_name = "test_tarball.tar.xz"
        tb_contents = "I'm a result!"

        def request_callback(request: requests.Request):
            if metadata:
                assert "metadata" in request.params
                assert request.params["metadata"] == metadata
            else:
                assert "metadata" not in request.params
            return HTTPStatus.CREATED, {}, ""

        uri = self.config.get("results", "server_rest_url")
        responses.add_callback(
            responses.PUT, f"{uri}/upload/{tb_name}", callback=request_callback
        )

        with monkeypatch.context() as m:
            m.setattr(Path, "exists", self.get_path_exists_mock(tb_name, True))
            m.setattr(
                Path, "open", self.get_path_open_mock(tb_name, io.StringIO(tb_contents))
            )

            res = CopyResultToServer(
                self.config, agent_logger, None, "token", "private", metadata
            ).push(Path(tb_name), "someMD5")

        assert res.status_code == HTTPStatus.CREATED

    @responses.activate
    @pytest.mark.parametrize("access", ("public", "private", None))
    def test_relay(self, access: str, monkeypatch, agent_logger):
        tb_name = "test_tarball.tar.xz"
        tb_contents = b"I'm a result!"
        metadata = ["dataset.name:foo", "global.server:FOO"]
        sha256 = hashlib.sha256(tb_contents, usedforsecurity=False).hexdigest()
        md5 = hashlib.md5(tb_contents, usedforsecurity=False).hexdigest()
        uri = "http://relay.example.com"

        manifest = {
            "metadata": metadata,
            "name": tb_name,
            "uri": f"{uri}/{sha256}",
            "md5": md5,
        }
        if access:
            manifest["access"] = access

        serialized = bytes(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        man_sha256 = hashlib.sha256(serialized, usedforsecurity=False).hexdigest()

        def man_callback(request: requests.PreparedRequest):
            assert json.load(fp=request.body) == manifest
            return HTTPStatus.CREATED, {}, ""

        def tar_callback(request: requests.PreparedRequest):
            assert request.headers["content-length"] == str(len(tb_contents))
            return HTTPStatus.CREATED, {}, ""

        responses.add_callback(
            responses.PUT, f"{uri}/{man_sha256}", callback=man_callback
        )
        responses.add_callback(responses.PUT, f"{uri}/{sha256}", callback=tar_callback)

        with monkeypatch.context() as m:
            m.setattr(Path, "exists", self.get_path_exists_mock(tb_name, True))
            m.setattr(
                Path, "open", self.get_path_open_mock(tb_name, io.BytesIO(tb_contents))
            )

            res = CopyResultToRelay(agent_logger, uri, access, metadata).push(
                Path(tb_name), md5
            )

        assert res.status_code == HTTPStatus.CREATED

    @responses.activate
    def test_connection_error(self, monkeypatch, agent_logger):
        tb_name = "test_tarball.tar.xz"
        tb_contents = "I'm a result!"
        uri = self.config.get("results", "server_rest_url")
        upload_url = f"{uri}/upload/{tb_name}"
        expected_error_message = f"Cannot connect to '{upload_url}'"
        responses.add(
            responses.PUT, upload_url, body=requests.exceptions.ConnectionError("uh-oh")
        )

        with monkeypatch.context() as m:
            m.setattr(Path, "exists", self.get_path_exists_mock(tb_name, True))
            m.setattr(
                Path, "open", self.get_path_open_mock(tb_name, io.StringIO(tb_contents))
            )

            with pytest.raises(RuntimeError) as excinfo:
                CopyResultToServer(
                    self.config, agent_logger, None, None, None, None
                ).push(Path(tb_name), "someMD5")

        assert str(excinfo.value).startswith(
            expected_error_message
        ), f"expected='...{expected_error_message}', found='{str(excinfo.value)}'"

    @responses.activate
    def test_unexpected_error(self, monkeypatch, agent_logger):
        tb_name = "test_tarball.tar.xz"
        tb_contents = "I'm a result!"
        uri = self.config.get("results", "server_rest_url")
        upload_url = f"{uri}/upload/{tb_name}"

        responses.add(responses.PUT, upload_url, body=RuntimeError("uh-oh"))

        with monkeypatch.context() as m:
            m.setattr(Path, "exists", self.get_path_exists_mock(tb_name, True))
            m.setattr(
                Path, "open", self.get_path_open_mock(tb_name, io.StringIO(tb_contents))
            )

            with pytest.raises(CopyResult.FileUploadError) as excinfo:
                CopyResultToServer(
                    self.config, agent_logger, None, None, None, None
                ).push(Path(tb_name), "someMD5")

        assert f"{upload_url!r} failed:" in str(excinfo.value)
