from http import HTTPStatus
from pathlib import Path

import pytest
import requests
import werkzeug.utils

from pbench.server.cache_manager import CacheManager
from pbench.server.database.models.dataset import Dataset, DatasetNotFound
from pbench.server.globals import server


class TestDatasetsAccess:
    def query_as_base(self, method, pbench_token):
        """
        Helper fixture to perform the API query and validate an expected
        return status.

        Args:
            method: client method to use for the API
            pbench_token: Authenticated user token fixture
        """

        def query_api(
            dataset: str, target: str, expected_status: HTTPStatus
        ) -> requests.Response:
            try:
                dataset_id = Dataset.query(name=dataset).resource_id
            except DatasetNotFound:
                dataset_id = dataset  # Allow passing deliberately bad value
            headers = {"authorization": f"bearer {pbench_token}"}
            k = "" if target is None else f"/{target}"
            response = method(
                f"{server.config.rest_uri}/datasets/inventory/{dataset_id}{k}",
                headers=headers,
            )
            assert response.status_code == expected_status
            return response

        return query_api

    @pytest.fixture
    def query_get_as(self, client, more_datasets, pbench_token):
        """Helper fixture to perform the GET API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            more_datasets: Dataset construction fixture
            pbench_token: Authenticated user token fixture
        """
        return self.query_as_base(client.get, pbench_token)

    @pytest.fixture
    def query_head_as(self, client, more_datasets, pbench_token):
        """Helper fixture to perform the HEAD API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            more_datasets: Dataset construction fixture
            pbench_token: Authenticated user token fixture
        """
        return self.query_as_base(client.head, pbench_token)

    def mock_find_dataset(self, dataset):
        class Tarball(object):
            unpacked = Path("/dataset/")
            tarball_path = Path("/dataset_tarball")

        # Validate the resource_id
        Dataset.query(resource_id=dataset)
        return Tarball

    def test_get_no_dataset(self, query_get_as):
        response = query_get_as(
            "nonexistent-dataset", "metadata.log", HTTPStatus.NOT_FOUND
        )
        assert response.json == {"message": "Dataset 'nonexistent-dataset' not found"}

    def test_dataset_not_present(self, query_get_as):
        response = query_get_as("fio_2", "metadata.log", HTTPStatus.NOT_FOUND)
        assert response.json == {
            "message": "The dataset tarball named 'random_md5_string4' is not present in the cache manager"
        }

    def test_unauthorized_access(self, query_get_as):
        response = query_get_as("test", "metadata.log", HTTPStatus.FORBIDDEN)
        assert response.json == {
            "message": "User drb is not authorized to READ a resource owned by test with private access"
        }

    def test_dataset_is_not_unpacked(self, query_get_as, monkeypatch):
        def mock_find_not_unpacked(self, dataset):
            class Tarball(object):
                unpacked = None

            # Validate the resource_id
            Dataset.query(resource_id=dataset)
            return Tarball

        monkeypatch.setattr(CacheManager, "find_dataset", mock_find_not_unpacked)

        response = query_get_as("fio_2", "1-default", HTTPStatus.NOT_FOUND)
        assert response.json == {"message": "The dataset is not unpacked"}

    def test_path_is_directory(self, query_get_as, monkeypatch):
        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        response = query_get_as("fio_2", "1-default", HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        assert response.json == {
            "message": "The specified path does not refer to a regular file"
        }

    def test_not_a_file(self, query_get_as, monkeypatch):
        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: False)

        response = query_get_as("fio_2", "1-default", HTTPStatus.NOT_FOUND)
        assert response.json == {
            "message": "The specified path does not refer to a file"
        }

    def test_dataset_in_given_path(self, query_get_as, monkeypatch):
        file_sent = None

        def mock_send_file(path_or_file, *args, **kwargs):
            nonlocal file_sent
            file_sent = path_or_file
            return {"status": "OK"}

        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: True)
        monkeypatch.setattr(werkzeug.utils, "send_file", mock_send_file)

        response = query_get_as("fio_2", "1-default/default.csv", HTTPStatus.OK)
        assert response.status_code == HTTPStatus.OK
        assert str(file_sent) == "/dataset/1-default/default.csv"

    @pytest.mark.parametrize("key", (None, ""))
    def test_get_result_tarball(self, query_get_as, monkeypatch, key):
        file_sent = None

        def mock_send_file(path_or_file, *args, **kwargs):
            nonlocal file_sent
            file_sent = path_or_file
            return {"status": "OK"}

        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: True)
        monkeypatch.setattr(werkzeug.utils, "send_file", mock_send_file)

        response = query_get_as("fio_2", key, HTTPStatus.OK)
        assert response.status_code == HTTPStatus.OK
        assert str(file_sent) == "/dataset_tarball"

    @pytest.mark.parametrize("key", (None, ""))
    def test_head_result_tarball(self, query_head_as, monkeypatch, key):
        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: True)

        response = query_head_as("fio_2", key, HTTPStatus.OK)
        assert response.status_code == HTTPStatus.OK
        assert response.get_data(as_text=True) == ""
