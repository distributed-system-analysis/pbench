from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from pquisby.lib.post_processing import QuisbyProcessing
import pytest
import requests

from pbench.server import JSON
from pbench.server.cache_manager import CacheExtractBadPath, CacheManager
from pbench.server.database.models.datasets import Dataset, DatasetNotFound, Metadata
from pbench.server.database.models.users import User


def mock_get_value(dataset: Dataset, key: str, user: Optional[User] = None) -> str:
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

        def filestream(self, _path: str) -> dict[str, Any]:
            return {"stream": BytesIO(b"CSV_file_as_a_string")}

    def mock_find_dataset(self, dataset) -> MockTarball:
        # Validate the resource_id
        Dataset.query(resource_id=dataset)
        return self.MockTarball()

    def test_dataset_not_present(self, query_get_as, monkeypatch):
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)

        query_get_as(["fio_2"], "drb", HTTPStatus.INTERNAL_SERVER_ERROR)

    def test_unsuccessful_get_with_incorrect_data(self, query_get_as, monkeypatch):
        def mock_filestream(_path: str) -> dict[str, Any]:
            return {"stream": BytesIO(b"IncorrectData")}

        def mock_compare_csv_to_json(
            self, benchmark_name, input_type, data_stream
        ) -> JSON:
            return {"status": "failed", "exception": "Unsupported Media Type"}

        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(CacheManager, "filestream", mock_filestream)
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)
        monkeypatch.setattr(
            QuisbyProcessing, "compare_csv_to_json", mock_compare_csv_to_json
        )
        query_get_as(["uperf_1", "uperf_2"], "test", HTTPStatus.INTERNAL_SERVER_ERROR)

    def test_tarball_unpack_exception(self, query_get_as, monkeypatch):
        def mock_filestream(path: str) -> dict[str, Any]:
            raise CacheExtractBadPath(Path("tarball"), path)

        monkeypatch.setattr(CacheManager, "find_dataset", self.mock_find_dataset)
        monkeypatch.setattr(self.MockTarball, "filestream", mock_filestream)
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)
        query_get_as(["uperf_1", "uperf_2"], "test", HTTPStatus.INTERNAL_SERVER_ERROR)

    @pytest.mark.parametrize(
        "user,datasets,exp_status,exp_message",
        (
            (
                "drb",
                ["uperf_1", "nonexistent-dataset"],
                HTTPStatus.BAD_REQUEST,
                "Unrecognized list value ['nonexistent-dataset'] given for parameter datasets; expected Dataset",
            ),
            (
                "drb",
                ["uperf_1", "uperf_2"],
                HTTPStatus.FORBIDDEN,
                "User drb is not authorized to READ a resource owned by test with private access",
            ),
            (
                "test",
                ["uperf_1", "uperf_2"],
                HTTPStatus.OK,
                None,
            ),
            (
                None,
                ["fio_1", "fio_2"],
                HTTPStatus.OK,
                None,
            ),
            (
                "test",
                ["fio_1", "uperf_3"],
                HTTPStatus.BAD_REQUEST,
                "Selected dataset benchmarks must match: uperf and hammerDB cannot be compared.",
            ),
            (
                "test",
                ["uperf_3", "uperf_4"],
                HTTPStatus.BAD_REQUEST,
                "Unsupported Benchmark: hammerDB",
            ),
        ),
    )
    def test_datasets_with_different_benchmark(
        self, user, datasets, exp_status, exp_message, query_get_as, monkeypatch
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

        response = query_get_as(datasets, user, exp_status)
        if exp_status == HTTPStatus.OK:
            assert response.json["status"] == "success"
            assert response.json["json_data"] == "quisby_data"
        else:
            assert response.json["message"] == exp_message
