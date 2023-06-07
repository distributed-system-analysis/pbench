from http import HTTPStatus
from pathlib import Path
import tarfile

import pytest
import requests

from pbench.server.cache_manager import CacheManager, Tarball
from pbench.server.database.models.datasets import Dataset, DatasetNotFound


class TestQuisbyResults:
    @pytest.fixture()
    def query_get_as(self, client, server_config, more_datasets, get_token_func):
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
            dataset: str, user, expected_status: HTTPStatus
        ) -> requests.Response:
            try:
                dataset_id = Dataset.query(name=dataset).resource_id
            except DatasetNotFound:
                dataset_id = dataset  # Allow passing deliberately bad value
            headers = {"authorization": f"bearer {get_token_func(user)}"}
            response = client.get(
                f"{server_config.rest_uri}/quisby/{dataset_id}/",
                headers=headers,
            )
            assert response.status_code == expected_status
            return response

        return query_api

    def mock_find_dataset(self, dataset):
        class Tarball(object):
            tarball_path = Path(
                "uperf_rhel8.1_4.18.0-107.el8_snap4_25gb_virt_2019.06.21T01.28.57.tar.xz"
            )

            def extract(tarball_path, path):
                mod_path = Path(__file__).parent
                relative_path_2 = "../../functional/server/tarballs/uperf_rhel8.1_4.18.0-107.el8_snap4_25gb_virt_2019.06.21T01.28.57.tar.xz"
                uperf_tarball_path = (mod_path / relative_path_2).resolve()
                tarball_path_1 = Path(uperf_tarball_path)
                tar = tarfile.open(tarball_path_1, "r:*")

                return (
                    tar.extractfile(
                        "uperf_rhel8.1_4.18.0-107.el8_snap4_25gb_virt_2019.06.21T01.28.57/result.csv"
                    )
                    .read()
                    .decode()
                )

        # Validate the resource_id
        Dataset.query(resource_id=dataset)
        return Tarball

    def test_get_no_dataset(self, query_get_as):
        response = query_get_as("nonexistent-dataset", "drb", HTTPStatus.NOT_FOUND)
        assert response.json == {"message": "Dataset 'nonexistent-dataset' not found"}

    def test_dataset_not_present(self, query_get_as):
        response = query_get_as("fio_2", "drb", HTTPStatus.NOT_FOUND)
        assert response.json == {
            "message": "The dataset tarball named 'random_md5_string4' is not present in the cache manager"
        }

    def test_unauthorized_access(self, query_get_as):
        response = query_get_as("test", "drb", HTTPStatus.FORBIDDEN)
        assert response.json == {
            "message": "User drb is not authorized to READ a resource owned by test with private access"
        }

    def test_quisby_success(self, query_get_as, monkeypatch):
        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)

        response = query_get_as("uperf_1", "test", HTTPStatus.OK)
        assert response.json["status"] == "success"
        assert response.json["jsonData"]

    def test_quisby_failure(self, query_get_as, monkeypatch):

        # Need to refine it
        def extract_csv(self):
            return "IncorrectData"

        monkeypatch.setattr(Tarball, "extract", extract_csv)
        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)

        response = query_get_as("uperf_1", "test", HTTPStatus.OK)
        print(response.json)
