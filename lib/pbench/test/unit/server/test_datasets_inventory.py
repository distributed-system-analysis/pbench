from http import HTTPStatus
import os
import werkzeug.utils
import typing as t
from datetime import datetime
from pathlib import Path

import pytest
import requests

if t.TYPE_CHECKING:
    from _typeshed.wsgi import WSGIEnvironment
    from flask.wrappers import Response

from pbench.server import PbenchServerConfig
from pbench.server.database.models.datasets import Dataset, DatasetNotFound
from pbench.server.filetree import FileTree


class TestDatasetsAccess:
    @pytest.fixture()
    def query_get_as(self, client, server_config, more_datasets, provide_metadata):
        """
        Helper fixture to perform the API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            server_config: Pbench config fixture
            more_datasets: Dataset construction fixture
            provide_metadata: Dataset metadata fixture
        """

        def query_api(
            dataset: str, username: str, expected_status: HTTPStatus, path: str
        ) -> requests.Response:
            headers = None
            try:
                dataset_id = Dataset.query(name=dataset).resource_id
            except DatasetNotFound:
                dataset_id = dataset  # Allow passing deliberately bad value
            if username:
                token = self.token(client, server_config, username)
                headers = {"authorization": f"bearer {token}"}
            response = client.get(
                f"{server_config.rest_uri}/datasets/inventory/{dataset_id}/{path}",
                headers=headers,
            )
            assert response.status_code == expected_status

            if username:
                client.post(
                    f"{server_config.rest_uri}/logout",
                    headers={"authorization": f"bearer {token}"},
                )
            return response

        return query_api

    def token(self, client, config: PbenchServerConfig, user: str) -> str:
        response = client.post(
            f"{config.rest_uri}/login",
            json={"username": user, "password": "12345"},
        )
        assert response.status_code == HTTPStatus.OK
        data = response.json
        assert data["auth_token"]
        return data["auth_token"]

    def mock_send_file(
        self,
        path_or_file: t.Union[os.PathLike, str, t.IO[bytes]],
        environ: "WSGIEnvironment",
        mimetype: t.Optional[str] = None,
        as_attachment: bool = False,
        download_name: t.Optional[str] = None,
        conditional: bool = True,
        etag: t.Union[bool, str] = True,
        last_modified: t.Optional[t.Union[datetime, int, float]] = None,
        max_age: t.Optional[
            t.Union[int, t.Callable[[t.Optional[str]], t.Optional[int]]]
        ] = None,
        use_x_sendfile: bool = False,
        response_class: t.Optional[t.Type["Response"]] = None,
        _root_path: t.Optional[t.Union[os.PathLike, str]] = None,
    ):
        return {"status": "OK"}

    def mock_find_dataset(self, dataset):
        class Tarball(object):
            unpacked = "/dataset1/"

        return Tarball

    def test_get_no_dataset(self, query_get_as):
        response = query_get_as(
            "nonexistent-dataset", "drb", HTTPStatus.NOT_FOUND, "metadata.log"
        )
        assert response.json == {"message": "Dataset 'nonexistent-dataset' not found"}

    def test_dataset_not_present(self, query_get_as, monkeypatch):
        response = query_get_as("fio_2", "test", HTTPStatus.NOT_FOUND, "metadata.log")
        assert response.json == {
            "message": "The dataset named 'fio_2' is not present in the file tree"
        }

    def test_path_is_directory(self, query_get_as, monkeypatch):
        monkeypatch.setattr(FileTree, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        response = query_get_as(
            "fio_2", "test", HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "1-default"
        )
        assert response.json == {
            "message": "The specified path does not refers to a regular file"
        }

    def test_not_a_file(self, query_get_as, monkeypatch):
        monkeypatch.setattr(FileTree, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: False)

        response = query_get_as("fio_2", "test", HTTPStatus.NOT_FOUND, "1-default")
        assert response.json == {"message": "File is not present in the given path"}

    def test_dataset_in_given_path(self, query_get_as, monkeypatch):
        monkeypatch.setattr(FileTree, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Path, "is_file", lambda self: True)
        monkeypatch.setattr(werkzeug.utils, "send_file", self.mock_send_file)

        response = query_get_as("fio_1", "drb", HTTPStatus.OK, "1-default/default.csv")
        assert response.status_code == HTTPStatus.OK
