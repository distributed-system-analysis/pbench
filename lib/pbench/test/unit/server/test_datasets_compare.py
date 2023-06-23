from http import HTTPStatus
from pathlib import Path

from pquisby.lib.post_processing import QuisbyProcessing
import pytest
import requests

from pbench.server import JSON
from pbench.server.cache_manager import CacheManager
from pbench.server.database.models.datasets import Dataset, DatasetNotFound, Metadata


def mock_get_value(dataset, key) -> str:
    if dataset.name == "uperf_3" or dataset.name == "uperf_4":
        return "hammerDB"
    return "uperf"


class TestCompareDatasets:
    @pytest.fixture()
    def query_get_as(self, client, server_config, more_datasets, get_token_func):
        """
        Helper fixture to perform the API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            server_config: Pbench config fixture
            more_datasets: Dataset construction fixture
            get_token_func: Pbench token fixture
        """

        def query_api(
            datasets: list, user: str, expected_status: HTTPStatus
        ) -> requests.Response:
            ds_list = []
            for dataset in datasets:
                try:
                    dataset_id = Dataset.query(name=dataset).resource_id
                    ds_list.append(dataset_id)
                except DatasetNotFound:
                    ds_list.append(dataset)  # Allow passing deliberately bad value
            headers = None
            if user:
                headers = {"authorization": f"bearer {get_token_func(user)}"}
            response = client.get(
                f"{server_config.rest_uri}/compare",
                query_string={"datasets": ds_list},
                headers=headers,
            )
            assert response.status_code == expected_status
            return response

        return query_api

    class MockTarball:
        tarball_path = Path("/dataset/tarball.tar.xz")
        name = "tarball"

        def extract(_tarball_path: Path, _path: str) -> str:
            return "CSV_file_as_a_string"

    def mock_find_dataset(self, dataset) -> MockTarball:
        # Validate the resource_id
        Dataset.query(resource_id=dataset)
        return self.MockTarball

    def test_get_no_dataset(self, query_get_as, monkeypatch):
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)

        response = query_get_as(
            ["uperf_1", "nonexistent-dataset"], "drb", HTTPStatus.BAD_REQUEST
        )
        assert (
            response.json["message"]
            == "Unrecognized list value ['nonexistent-dataset'] given for parameter datasets; expected Dataset"
        )

    def test_dataset_not_present(self, query_get_as, monkeypatch):
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)

        query_get_as(["fio_2"], "drb", HTTPStatus.INTERNAL_SERVER_ERROR)

    def test_unauthorized_access(self, query_get_as, monkeypatch):
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)

        response = query_get_as(["uperf_1", "uperf_2"], "drb", HTTPStatus.FORBIDDEN)
        assert response.json == {
            "message": "User drb is not authorized to READ a resource owned by test with private access"
        }

    def test_unsupported_benchmark(self, query_get_as, monkeypatch):
        extract_data_called = False

        def mock_compare_csv_to_json(*args, **kwargs):
            nonlocal extract_data_called
            extract_data_called = True

        class MockTarball:
            tarball_path = Path("/dataset/tarball.tar.xz")
            name = "tarball"

            def extract(_tarball_path: Path, _path: str) -> str:
                return "IncorrectData"

        def mock_find_dataset_with_incorrect_data(self, dataset) -> MockTarball:
            # Validate the resource_id
            Dataset.query(resource_id=dataset)
            return MockTarball

        monkeypatch.setattr(
            CacheManager, "find_dataset", mock_find_dataset_with_incorrect_data
        )
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)
        monkeypatch.setattr(
            QuisbyProcessing, "compare_csv_to_json", mock_compare_csv_to_json
        )
        response = query_get_as(
            ["uperf_3", "uperf_4"], "test", HTTPStatus.UNSUPPORTED_MEDIA_TYPE
        )
        assert response.json["message"] == "Unsupported Benchmark: hammerDB"
        assert not extract_data_called

    def test_successful_get(self, query_get_as, monkeypatch):
        def mock_compare_csv_to_json(
            self, benchmark_name, input_type, data_stream
        ) -> JSON:
            return {"status": "success", "json_data": "quisby_data"}

        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)
        monkeypatch.setattr(
            QuisbyProcessing, "compare_csv_to_json", mock_compare_csv_to_json
        )

        response = query_get_as(["uperf_1", "uperf_2"], "test", HTTPStatus.OK)
        assert response.json["status"] == "success"
        assert response.json["json_data"] == "quisby_data"

    def test_unauthorized_user_compares_public_datasets(
        self, query_get_as, monkeypatch
    ):
        def mock_compare_csv_to_json(
            self, benchmark_name, input_type, data_stream
        ) -> JSON:
            return {"status": "success", "json_data": "quisby_data"}

        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)
        monkeypatch.setattr(
            QuisbyProcessing, "compare_csv_to_json", mock_compare_csv_to_json
        )

        response = query_get_as(["fio_1", "fio_2"], None, HTTPStatus.OK)
        assert response.json["status"] == "success"
        assert response.json["json_data"] == "quisby_data"

    def test_unsuccessful_get_with_incorrect_data(self, query_get_as, monkeypatch):
        def mock_find_dataset_with_incorrect_data(self, dataset):
            class MockTarball(object):
                tarball_path = Path("/dataset/tarball.tar.xz")

                def extract(tarball_path, path) -> str:
                    return "IncorrectData"

            return MockTarball

        def mock_compare_csv_to_json(
            self, benchmark_name, input_type, data_stream
        ) -> JSON:
            return {"status": "failed", "exception": "Unsupported Media Type"}

        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)
        monkeypatch.setattr(
            QuisbyProcessing, "compare_csv_to_json", mock_compare_csv_to_json
        )
        query_get_as(["uperf_1", "uperf_2"], "test", HTTPStatus.INTERNAL_SERVER_ERROR)

    def test_datasets_with_different_benchmark(self, query_get_as, monkeypatch):
        def mock_compare_csv_to_json(
            self, benchmark_name, input_type, data_stream
        ) -> JSON:
            return {"status": "success", "json_data": "quisby_data"}

        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)
        monkeypatch.setattr(
            QuisbyProcessing, "compare_csv_to_json", mock_compare_csv_to_json
        )

        response = query_get_as(["fio_1", "uperf_3"], "test", HTTPStatus.BAD_REQUEST)
        assert (
            response.json["message"]
            == "Requested datasets must all use the same benchmark; found references to uperf and hammerDB."
        )
