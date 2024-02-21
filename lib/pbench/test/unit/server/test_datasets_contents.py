from http import HTTPStatus
from pathlib import Path
from typing import Optional

import pytest
import requests

from pbench.server.cache_manager import BadDirpath, CacheManager
from pbench.server.database.models.datasets import Dataset, DatasetNotFound


class TestDatasetsContents:
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
                f"{server_config.rest_uri}/datasets/{dataset_id}/contents/{target}",
                headers=headers,
            )
            assert (
                response.status_code == expected_status
            ), f"Unexpected failure '{response.json}'"
            return response

        return query_api

    def test_get_no_dataset(self, query_get_as):
        """This fails in Dataset SQL lookup"""
        response = query_get_as(
            "nonexistent-dataset", "metadata.log", HTTPStatus.NOT_FOUND
        )
        assert response.json == {"message": "Dataset 'nonexistent-dataset' not found"}

    def test_dataset_not_present(self, query_get_as):
        """This fails in the cache manager find_dataset as there are none"""
        response = query_get_as("fio_2", "metadata.log", HTTPStatus.NOT_FOUND)
        assert response.json == {
            "message": "The dataset tarball named 'random_md5_string4' is not found"
        }

    def test_unauthorized_access(self, query_get_as):
        """This fails because our default user can't read the 'test' dataset"""
        response = query_get_as("test", "metadata.log", HTTPStatus.FORBIDDEN)
        assert response.json == {
            "message": "User drb is not authorized to READ a resource owned by test with private access"
        }

    def test_contents_error(self, monkeypatch, query_get_as):
        """This fails with an internal error from get_contents"""

        def mock_contents(_s, _d, _p, _o):
            raise Exception("Nobody expected me")

        monkeypatch.setattr(CacheManager, "get_contents", mock_contents)
        query_get_as("drb", "metadata.log", HTTPStatus.INTERNAL_SERVER_ERROR)

    def test_jsonify_error(self, monkeypatch, query_get_as):
        """This fails with an internal error from jsonifying bad data"""

        monkeypatch.setattr(
            CacheManager, "get_contents", lambda _s, _d, _p, _o: {1: 0, Path("."): "a"}
        )
        query_get_as("drb", "metadata.log", HTTPStatus.INTERNAL_SERVER_ERROR)

    @pytest.mark.parametrize("key", ("", ".", "subdir1"))
    def test_path_is_directory(self, query_get_as, monkeypatch, key):
        """Mock a directory cache node to check that data is passed through"""
        name = "" if key == "." else key
        contents = {
            "directories": [],
            "files": [],
            "uri": f"https://localhost/api/v1/datasets/random_md5_string4/contents/{name}",
        }

        monkeypatch.setattr(CacheManager, "get_contents", lambda s, d, p, o: contents)
        response = query_get_as("fio_2", key, HTTPStatus.OK)
        assert response.json == contents

    def test_not_a_file(self, query_get_as, monkeypatch):
        """When 'get_contents' fails with an exception, we report the text"""

        def mock_get_contents(_s, _d: str, _p: Optional[Path], _o: str):
            raise BadDirpath("Nobody home")

        monkeypatch.setattr(CacheManager, "get_contents", mock_get_contents)
        response = query_get_as("fio_2", "subdir1/f1_sym", HTTPStatus.NOT_FOUND)
        assert response.json == {"message": "Nobody home"}

    def test_file_info(self, query_get_as, monkeypatch):
        """Mock a file cache node to check check that data is passed through"""
        name = "f1.json"
        file_data = {
            "name": name,
            "size": 16,
            "type": "FILE",
            "uri": f"https://localhost/api/v1/datasets/random_md5_string4/inventory/{name}",
        }
        monkeypatch.setattr(CacheManager, "get_contents", lambda s, d, p, o: file_data)
        response = query_get_as("fio_2", name, HTTPStatus.OK)
        assert response.status_code == HTTPStatus.OK
        assert response.json == file_data
