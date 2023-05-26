from http import HTTPStatus
from pathlib import Path

import pytest
import requests
import werkzeug.utils

from pbench.server.cache_manager import CacheManager
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
            k = "" if target is None else f"/{target}"
            response = client.get(
                f"{server_config.rest_uri}/datasets/{dataset_id}/inventory{k}",
                headers=headers,
            )
            assert response.status_code == expected_status
            return response

        return query_api

    def mock_find_dataset(self, dataset):
        class Tarball(object):
            unpacked = Path("/dataset/")
            tarball_path = Path("/dataset/tarball.tar.xz")

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
        def mock_send_file(path_or_file, *args, **kwargs):
            assert str(path_or_file) == "/dataset/1-default/default.csv"
            assert kwargs["as_attachment"] is False
            assert kwargs["download_name"] == "default.csv"
            return {"status": "OK"}

        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: True)
        monkeypatch.setattr(werkzeug.utils, "send_file", mock_send_file)

        response = query_get_as("fio_2", "1-default/default.csv", HTTPStatus.OK)
        assert response.status_code == HTTPStatus.OK

    @pytest.mark.parametrize("key", (None, ""))
    def test_get_result_tarball(self, query_get_as, monkeypatch, key):
        def mock_send_file(path_or_file, *args, **kwargs):
            assert str(path_or_file) == "/dataset/tarball.tar.xz"
            assert kwargs["as_attachment"] is True
            assert kwargs["download_name"] == "tarball.tar.xz"
            return {"status": "OK"}

        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: True)
        monkeypatch.setattr(werkzeug.utils, "send_file", mock_send_file)

        response = query_get_as("fio_2", key, HTTPStatus.OK)
        assert response.status_code == HTTPStatus.OK
