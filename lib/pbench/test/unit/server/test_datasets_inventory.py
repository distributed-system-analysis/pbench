from http import HTTPStatus
import io
from pathlib import Path
from typing import Callable, Optional

from flask import Response
import pytest
import requests

from pbench.server import JSONOBJECT
from pbench.server.cache_manager import (
    CacheExtractError,
    CacheManager,
    CacheType,
    Inventory,
)
from pbench.server.database.models.datasets import Dataset, DatasetNotFound


class TestDatasetsAccess:
    @pytest.fixture()
    def query_get_as(self, client, server_config, more_datasets, pbench_drb_token):
        """
        Helper fixture to perform the API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            server_config: Pbench config fixture
            more_datasets: Dataset construction fixture
            pbench_drb_token: Authenticated user token fixture
        """

        def query_api(
            dataset: str, target: str, expected_status: HTTPStatus
        ) -> requests.Response:
            try:
                dataset_id = Dataset.query(name=dataset).resource_id
            except DatasetNotFound:
                dataset_id = dataset  # Allow passing deliberately bad value
            headers = {"authorization": f"bearer {pbench_drb_token}"}
            t = target if target else ""
            response = client.get(
                f"{server_config.rest_uri}/datasets/{dataset_id}/inventory/{t}",
                headers=headers,
            )
            assert response.status_code == expected_status
            return response

        return query_api

    def test_get_no_dataset(self, query_get_as):
        response = query_get_as(
            "nonexistent-dataset", "metadata.log", HTTPStatus.NOT_FOUND
        )
        assert response.json == {"message": "Dataset 'nonexistent-dataset' not found"}

    def test_dataset_not_present(self, query_get_as):
        response = query_get_as("fio_2", "metadata.log", HTTPStatus.NOT_FOUND)
        assert response.json == {
            "message": "The dataset tarball named 'random_md5_string4' is not found"
        }

    def test_unauthorized_access(self, query_get_as):
        response = query_get_as("test", "metadata.log", HTTPStatus.FORBIDDEN)
        assert response.json == {
            "message": "User drb is not authorized to READ a resource owned by test with private access"
        }

    @pytest.mark.parametrize("key", (None, "", "subdir1"))
    def test_path_is_directory(self, server_config, query_get_as, monkeypatch, key):
        def mock_get_inventory(_s, _d: str, _t: str):
            return {"type": CacheType.DIRECTORY, "stream": None}

        monkeypatch.setattr(CacheManager, "get_inventory", mock_get_inventory)
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        response = query_get_as("fio_2", key, HTTPStatus.MOVED_PERMANENTLY)
        uri = "https://localhost/api/v1/datasets/random_md5_string4/contents/"
        assert response.headers["location"] == uri + (key if key else "")

    def test_not_a_file(self, query_get_as, monkeypatch):
        def mock_get_inventory(_s, _d: str, _t: str):
            return {"type": CacheType.SYMLINK, "stream": None}

        monkeypatch.setattr(CacheManager, "get_inventory", mock_get_inventory)
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: False)

        response = query_get_as("fio_2", "subdir1/f1_sym", HTTPStatus.BAD_REQUEST)
        assert response.json == {
            "message": "The specified path does not refer to a regular file"
        }

    @pytest.mark.parametrize(
        "status,exception,message",
        (
            (
                HTTPStatus.NOT_FOUND,
                CacheExtractError("fio_2", "target"),
                "Unable to read 'target' from fio_2",
            ),
            (
                HTTPStatus.INTERNAL_SERVER_ERROR,
                Exception("I'm something else!"),
                "Internal Pbench Server Error: log reference ",
            ),
        ),
    )
    def test_get_inventory_raises(
        self, query_get_as, monkeypatch, status, exception, message
    ):
        def mock_get_inventory(_s, _d: str, _t: str):
            raise exception

        monkeypatch.setattr(CacheManager, "get_inventory", mock_get_inventory)
        response = query_get_as("fio_2", "target", status)
        assert response.json["message"].startswith(message)

    def test_dataset_in_given_path(self, query_get_as, monkeypatch):
        mock_close = False

        def call_on_close(_c: Callable):
            nonlocal mock_close
            mock_close = True

        mock_args: Optional[tuple[Path, JSONOBJECT]] = None
        exp_stream = io.BytesIO(b"file_as_a_byte_stream")

        def mock_get_inventory(_s, _d: str, _t: str):
            return {
                "name": "f1.json",
                "type": CacheType.FILE,
                "stream": Inventory(exp_stream),
            }

        response = Response()
        monkeypatch.setattr(response, "call_on_close", call_on_close)

        def mock_send_file(path_or_file, *args, **kwargs):
            nonlocal mock_args
            mock_args = (path_or_file, kwargs)
            return response

        monkeypatch.setattr(CacheManager, "get_inventory", mock_get_inventory)
        monkeypatch.setattr(
            "pbench.server.api.resources.datasets_inventory.send_file", mock_send_file
        )

        response = query_get_as("fio_2", "f1.json", HTTPStatus.OK)
        assert response.status_code == HTTPStatus.OK

        file_content, args = mock_args

        assert isinstance(file_content, Inventory)
        assert file_content.stream == exp_stream
        assert args["as_attachment"] is False
        assert args["download_name"] == "f1.json"
        assert mock_close

    @pytest.mark.parametrize("stream", (io.BytesIO(b"file_as_a_byte_stream"), None))
    def test_send_fail(self, query_get_as, monkeypatch, stream):
        """Test handling of stream when send_file fails.

        (Note that while the mocking when "stream" is None doesn't really do
        much, we gain coverage of both `if stream` paths.)
        """
        mock_closed = False

        def mock_close(*_args):
            nonlocal mock_closed
            mock_closed = True

        def mock_get_inventory(_s, _d: str, _t: str):
            return {
                "name": "f1.json",
                "type": CacheType.FILE,
                "stream": Inventory(stream) if stream else None,
            }

        def mock_send_file(path_or_file, *args, **kwargs):
            raise Exception("I'm failing to succeed")

        monkeypatch.setattr(Inventory, "close", mock_close)
        monkeypatch.setattr(CacheManager, "get_inventory", mock_get_inventory)
        monkeypatch.setattr(
            "pbench.server.api.resources.datasets_inventory.send_file", mock_send_file
        )

        query_get_as("fio_2", "f1.json", HTTPStatus.INTERNAL_SERVER_ERROR)
        assert mock_closed is bool(stream)

    def test_get_inventory(self, query_get_as, monkeypatch):
        exp_stream = io.BytesIO(b"file_as_a_byte_stream")

        def mock_get_inventory(_s, _d: str, _t: str):
            return {
                "name": "f1.json",
                "type": CacheType.FILE,
                "stream": Inventory(exp_stream),
            }

        monkeypatch.setattr(CacheManager, "get_inventory", mock_get_inventory)
        response = query_get_as("fio_2", "f1.json", HTTPStatus.OK)
        assert response.status_code == HTTPStatus.OK
        assert response.text == "file_as_a_byte_stream"
        assert response.headers["content-type"] == "application/json"
        assert response.headers["content-disposition"] == "inline; filename=f1.json"
