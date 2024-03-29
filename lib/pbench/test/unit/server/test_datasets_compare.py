from http import HTTPStatus
from pathlib import Path
from typing import Optional

import pytest
import requests

from pbench.server import JSON
from pbench.server.cache_manager import CacheExtractBadPath, CacheManager
from pbench.server.database.models.datasets import Dataset, DatasetNotFound, Metadata
from pbench.server.database.models.users import User

real_getvalue = Metadata.getvalue


def mock_get_value(dataset: Dataset, key: str, user: Optional[User] = None) -> JSON:
    if key == Metadata.SERVER_BENCHMARK:
        return "hammerDB" if dataset.name in ("uperf_3", "uperf_4") else "uperf"
    return real_getvalue(dataset, key, user)


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

    def test_no_postprocessed_data(self, query_get_as, monkeypatch):
        """Test with an unknown benchmark"""
        fio_2 = Dataset.query(name="fio_2")
        Metadata.setvalue(
            fio_2, Metadata.SERVER_BENCHMARK, Metadata.SERVER_BENCHMARK_UNKNOWN
        )
        query_get_as(["fio_2"], "drb", HTTPStatus.BAD_REQUEST)

    def test_with_incorrect_data(self, query_get_as, monkeypatch):
        """Quisby processing fails"""

        def mock_get_inventory_bytes(_self, _dataset: str, _path: str) -> str:
            return "IncorrectData"

        class MockQuisby:
            def compare_csv_to_json(self, _b, _i, _d) -> JSON:
                return {"status": "failed", "exception": "Unsupported Media Type"}

        monkeypatch.setattr(
            CacheManager, "get_inventory_bytes", mock_get_inventory_bytes
        )
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)
        monkeypatch.setattr(
            "pbench.server.api.resources.datasets_compare.QuisbyProcessing", MockQuisby
        )
        response = query_get_as(
            ["uperf_1", "uperf_2"], "test", HTTPStatus.INTERNAL_SERVER_ERROR
        )
        assert response.json["message"].startswith(
            "Internal Pbench Server Error: log reference "
        )

    def test_quisby_exception(self, query_get_as, monkeypatch):
        """Quisby processing raises an exception"""

        def mock_get_inventory_bytes(_self, _dataset: str, _path: str) -> str:
            return "arbitraryData"

        class MockQuisby:
            def compare_csv_to_json(self, _b, _i, _d) -> JSON:
                raise Exception("I'm not in the mood")

        monkeypatch.setattr(
            CacheManager, "get_inventory_bytes", mock_get_inventory_bytes
        )
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)
        monkeypatch.setattr(
            "pbench.server.api.resources.datasets_compare.QuisbyProcessing", MockQuisby
        )
        response = query_get_as(
            ["uperf_1", "uperf_2"], "test", HTTPStatus.INTERNAL_SERVER_ERROR
        )
        assert response.json["message"].startswith(
            "Internal Pbench Server Error: log reference "
        )

    def test_get_inventory_exception(self, query_get_as, monkeypatch):
        def mock_get_inventory_bytes(_self, _dataset: str, _path: str) -> str:
            raise CacheExtractBadPath(Path("tarball"), _path)

        monkeypatch.setattr(
            CacheManager, "get_inventory_bytes", mock_get_inventory_bytes
        )
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)
        query_get_as(["uperf_1", "uperf_2"], "test", HTTPStatus.BAD_REQUEST)

    def test_get_inventory_unexpected_exception(self, query_get_as, monkeypatch):
        def mock_get_inventory_bytes(_self, _dataset: str, _path: str) -> str:
            raise OSError()

        monkeypatch.setattr(
            CacheManager, "get_inventory_bytes", mock_get_inventory_bytes
        )
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
        class MockQuisby:
            def compare_csv_to_json(self, _b, _i, _d) -> JSON:
                return {"status": "success", "json_data": "quisby_data"}

        def mock_get_inventory_bytes(_self, _dataset: str, _path: str) -> str:
            return "IncorrectData"

        monkeypatch.setattr(
            CacheManager, "get_inventory_bytes", mock_get_inventory_bytes
        )
        monkeypatch.setattr(Metadata, "getvalue", mock_get_value)
        monkeypatch.setattr(
            "pbench.server.api.resources.datasets_compare.QuisbyProcessing", MockQuisby
        )

        response = query_get_as(datasets, user, exp_status)
        if exp_status == HTTPStatus.OK:
            assert response.json["status"] == "success"
            assert response.json["benchmark"] == "uperf"
            assert response.json["json_data"] == "quisby_data"
        else:
            assert response.json["message"] == exp_message
