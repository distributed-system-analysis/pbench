from http import HTTPStatus
import os
import werkzeug.utils
from datetime import datetime
from pathlib import Path
from typing import Callable, IO, Optional, Type, TYPE_CHECKING, Union

import pytest
import requests

if TYPE_CHECKING:
    from _typeshed.wsgi import WSGIEnvironment
    from flask.wrappers import Response

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
        """

        def query_api(
            dataset: str, expected_status: HTTPStatus, path: str
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

    def mock_send_file(
        self,
        path_or_file: Union[os.PathLike, str, IO[bytes]],
        environ: "WSGIEnvironment",
        mimetype: Optional[str] = None,
        as_attachment: bool = False,
        download_name: Optional[str] = None,
        conditional: bool = True,
        etag: Union[bool, str] = True,
        last_modified: Optional[Union[datetime, int, float]] = None,
        max_age: Optional[Union[int, Callable[[Optional[str]], Optional[int]]]] = None,
        use_x_sendfile: bool = False,
        response_class: Optional[Type["Response"]] = None,
        _root_path: Optional[Union[os.PathLike, str]] = None,
    ):
        return {"status": "OK"}

    def mock_find_dataset(self, dataset):
        class Tarball(object):
            unpacked = "/dataset1/"

        return Tarball

    def test_get_no_dataset(self, query_get_as):
        response = query_get_as(
            "nonexistent-dataset", HTTPStatus.NOT_FOUND, "metadata.log"
        )
        assert response.json == {"message": "Dataset 'nonexistent-dataset' not found"}

    def test_dataset_not_present(self, query_get_as):
        response = query_get_as("fio_2", HTTPStatus.NOT_FOUND, "metadata.log")
        assert response.json == {
            "message": "The dataset tarball named 'fio_2' is not present in the file tree"
        }

    def test_unauthorized_access(self, query_get_as):
        response = query_get_as("test", HTTPStatus.FORBIDDEN, "metadata.log")
        assert response.json == {
            "message": "User drb is not authorized to READ a resource owned by test with private access"
        }

    def test_dataset_is_not_unpacked(self, query_get_as, monkeypatch):
        def mock_find_not_unpacked(self, dataset):
            class Tarball(object):
                unpacked = None

            return Tarball

        monkeypatch.setattr(FileTree, "find_dataset", mock_find_not_unpacked)

        response = query_get_as("fio_2", HTTPStatus.NOT_FOUND, "1-default")
        assert response.json == {"message": "The dataset is not unpacked"}

    def test_path_is_directory(self, query_get_as, monkeypatch):
        monkeypatch.setattr(FileTree, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        response = query_get_as("fio_2", HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "1-default")
        assert response.json == {
            "message": "The specified path does not refer to a regular file"
        }

    def test_not_a_file(self, query_get_as, monkeypatch):
        monkeypatch.setattr(FileTree, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: False)

        response = query_get_as("fio_2", HTTPStatus.NOT_FOUND, "1-default")
        assert response.json == {
            "message": "The specified path does not refer to a file"
        }

    def test_dataset_in_given_path(self, query_get_as, monkeypatch):
        monkeypatch.setattr(FileTree, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: True)
        monkeypatch.setattr(werkzeug.utils, "send_file", self.mock_send_file)

        response = query_get_as("fio_2", HTTPStatus.OK, "1-default/default.csv")
        assert response.status_code == HTTPStatus.OK
