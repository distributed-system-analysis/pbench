from http import HTTPStatus
from pathlib import Path

import pytest
import requests
import werkzeug.utils

from pbench.server.database.models.datasets import Dataset, DatasetNotFound
from pbench.server.filetree import FileTree


class TestDatasetsAccess:
    @pytest.fixture()
    def query_get_as(self, client, server_config, more_datasets, pbench_token):
        """
        Helper fixture to perform the API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            server_config: Pbench config fixture
            more_datasets: Dataset construction fixture
            pbench_token: Authenticated user token fixture
        """

        def query_api(
            dataset: str, path: str, expected_status: HTTPStatus
        ) -> requests.Response:
            try:
                dataset_id = Dataset.query(name=dataset).resource_id
            except DatasetNotFound:
                dataset_id = dataset  # Allow passing deliberately bad value
            headers = {"authorization": f"bearer {pbench_token}"}
            response = client.get(
                f"{server_config.rest_uri}/datasets/inventory/{dataset_id}/{path}",
                headers=headers,
            )
            assert response.status_code == expected_status
            return response

        return query_api

    def mock_find_dataset(self, dataset):
        class Tarball(object):
            unpacked = Path("/dataset1/")
            tarball_path = Path("/dataset1/")

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
            "message": "The dataset tarball named 'random_md5_string4' is not present in the file tree"
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

        monkeypatch.setattr(FileTree, "find_dataset", mock_find_not_unpacked)

        response = query_get_as("fio_2", "1-default", HTTPStatus.NOT_FOUND)
        assert response.json == {"message": "The dataset is not unpacked"}

    def test_path_is_directory(self, query_get_as, monkeypatch):
        monkeypatch.setattr(FileTree, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        response = query_get_as("fio_2", "1-default", HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        assert response.json == {
            "message": "The specified path does not refer to a regular file"
        }

    def test_not_a_file(self, query_get_as, monkeypatch):
        monkeypatch.setattr(FileTree, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: False)

        response = query_get_as("fio_2", "1-default", HTTPStatus.NOT_FOUND)
        assert response.json == {
            "message": "The specified path does not refer to a file"
        }

    def test_dataset_in_given_path(self, query_get_as, monkeypatch):
        monkeypatch.setattr(FileTree, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: True)
        monkeypatch.setattr(
            werkzeug.utils, "send_file", lambda *args, **kwargs: {"status": "OK"}
        )
        response = query_get_as("fio_2", "1-default/default.csv", HTTPStatus.OK)
        assert response.status_code == HTTPStatus.OK

    def test_get_result_tarball(self, query_get_as, monkeypatch):
        monkeypatch.setattr(FileTree, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(
            werkzeug.utils, "send_file", lambda *args, **kwargs: {"status": "OK"}
        )
        response = query_get_as("fio_2", "", HTTPStatus.OK)
        assert response.status_code == HTTPStatus.OK
