from http import HTTPStatus
import io
from pathlib import Path
from typing import Callable, Optional

from flask import Response
import pytest
import requests

from pbench.server import JSONOBJECT
from pbench.server.cache_manager import CacheManager, CacheType, Inventory
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
            response = client.get(
                f"{server_config.rest_uri}/datasets/{dataset_id}/inventory/{target}",
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
    def test_path_is_directory(self, query_get_as, monkeypatch, key):
        def mock_get_inventory(_s, _d: str, _t: str):
            return {"type": CacheType.DIRECTORY, "stream": None}

        monkeypatch.setattr(CacheManager, "get_inventory", mock_get_inventory)
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        response = query_get_as("fio_2", key, HTTPStatus.BAD_REQUEST)
        assert response.json == {
            "message": "The specified path does not refer to a regular file"
        }

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
                "stream": Inventory(exp_stream, None),
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
