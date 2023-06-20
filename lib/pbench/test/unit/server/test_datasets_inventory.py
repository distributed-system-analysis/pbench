from http import HTTPStatus
from pathlib import Path
from typing import Any, Optional

import pytest
import requests

from pbench.server.cache_manager import CacheManager, CacheType, Controller
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

    class MockTarball:
        def __init__(self, path: Path, controller: Controller):
            self.name = "dir_name.tar.xz"
            self.tarball_path = path
            self.unpacked = None

        def filestream(self, target):
            info = {
                "name": "f1.json",
                "type": CacheType.FILE,
                "stream": "file_as_a_byte_stream",
            }
            return info

    def mock_find_dataset(self, dataset):
        # Validate the resource_id
        Dataset.query(resource_id=dataset)
        return self.MockTarball(Path("/mock/dir_name.tar.xz"), "abc")

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
        filestream_tuple = {"type": CacheType.DIRECTORY, "stream": None}
        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(
            self.MockTarball, "filestream", lambda _s, _t: filestream_tuple
        )
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        response = query_get_as("fio_2", key, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        assert response.json == {
            "message": "The specified path does not refer to a regular file"
        }

    def test_not_a_file(self, query_get_as, monkeypatch):
        filestream_tuple = {"type": CacheType.SYMLINK, "stream": None}
        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(
            self.MockTarball, "filestream", lambda _s, _t: filestream_tuple
        )
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: False)

        response = query_get_as(
            "fio_2", "subdir1/f1_sym", HTTPStatus.UNSUPPORTED_MEDIA_TYPE
        )
        assert response.json == {
            "message": "The specified path does not refer to a regular file"
        }

    def test_dataset_in_given_path(self, query_get_as, monkeypatch):
        mock_args: Optional[tuple[Path, dict[str, Any]]] = None

        def mock_send_file(path_or_file, *args, **kwargs):
            nonlocal mock_args
            mock_args = (path_or_file, kwargs)
            return {"status": "OK"}

        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: True)
        monkeypatch.setattr(
            "pbench.server.api.resources.datasets_inventory.send_file", mock_send_file
        )

        response = query_get_as("fio_2", "f1.json", HTTPStatus.OK)
        assert response.status_code == HTTPStatus.OK

        file_content, args = mock_args

        assert str(file_content) == "file_as_a_byte_stream"
        assert args["as_attachment"] is False
        assert args["download_name"] == "f1.json"
