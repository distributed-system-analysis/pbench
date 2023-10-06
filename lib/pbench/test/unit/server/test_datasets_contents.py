from http import HTTPStatus
from pathlib import Path
from typing import Optional

import pytest
import requests

from pbench.server.cache_manager import BadDirpath, CacheManager, CacheObject, CacheType
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
                f"{server_config.rest_uri}/datasets/{dataset_id}/contents/{target}",
                headers=headers,
            )
            assert (
                response.status_code == expected_status
            ), f"Unexpected failure '{response.json}'"
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
        def mock_find_entry(_s, _d: str, path: Optional[Path]):
            file = path if path else Path("")
            return {
                "children": {},
                "details": CacheObject(
                    file.name if key else "",
                    file,
                    None,
                    None,
                    None,
                    CacheType.DIRECTORY,
                ),
            }

        monkeypatch.setattr(CacheManager, "find_entry", mock_find_entry)
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: True)

        response = query_get_as("fio_2", key if key else "", HTTPStatus.OK)
        assert response.json == {
            "directories": [],
            "files": [],
            "name": key if key else "",
            "type": "DIRECTORY",
            "uri": f"https://localhost/api/v1/datasets/random_md5_string4/contents/{key if key else ''}",
        }

    def test_not_a_file(self, query_get_as, monkeypatch):
        def mock_find_entry(_s, _d: str, path: Optional[Path]):
            raise BadDirpath("Nobody home")

        monkeypatch.setattr(CacheManager, "find_entry", mock_find_entry)
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        monkeypatch.setattr(Path, "exists", lambda self: False)

        response = query_get_as("fio_2", "subdir1/f1_sym", HTTPStatus.NOT_FOUND)
        assert response.json == {"message": "Nobody home"}

    def test_file_info(self, query_get_as, monkeypatch):
        name = "f1.json"

        def mock_find_entry(_s, _d: str, path: Optional[Path]):
            return {
                "details": CacheObject(path.name, path, None, None, 16, CacheType.FILE)
            }

        monkeypatch.setattr(CacheManager, "find_entry", mock_find_entry)
        response = query_get_as("fio_2", name, HTTPStatus.OK)
        assert response.status_code == HTTPStatus.OK
        assert response.json == {
            "name": name,
            "size": 16,
            "type": "FILE",
            "uri": f"https://localhost/api/v1/datasets/random_md5_string4/inventory/{name}",
        }

    def test_dir_info(self, query_get_as, monkeypatch):
        def mock_find_entry(_s, _d: str, path: Optional[Path]):
            base = path if path else Path("")
            return {
                "children": {
                    "default": {
                        "details": CacheObject(
                            "default",
                            base / "default",
                            None,
                            None,
                            None,
                            CacheType.DIRECTORY,
                        )
                    },
                    "file.txt": {
                        "details": CacheObject(
                            "file.txt",
                            base / "file.txt",
                            None,
                            None,
                            42,
                            CacheType.FILE,
                        )
                    },
                },
                "details": CacheObject(
                    base.name, base, None, None, None, CacheType.DIRECTORY
                ),
            }

        monkeypatch.setattr(CacheManager, "find_entry", mock_find_entry)
        response = query_get_as("fio_2", "sample1", HTTPStatus.OK)
        assert response.status_code == HTTPStatus.OK
        assert response.json == {
            "directories": [
                {
                    "name": "default",
                    "type": "DIRECTORY",
                    "uri": "https://localhost/api/v1/datasets/random_md5_string4/contents/sample1/default",
                }
            ],
            "files": [
                {
                    "name": "file.txt",
                    "size": 42,
                    "type": "FILE",
                    "uri": "https://localhost/api/v1/datasets/random_md5_string4/inventory/sample1/file.txt",
                }
            ],
            "name": "sample1",
            "type": "DIRECTORY",
            "uri": "https://localhost/api/v1/datasets/random_md5_string4/contents/sample1",
        }
