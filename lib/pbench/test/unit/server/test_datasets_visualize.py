from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import Optional

from pquisby.lib.post_processing import QuisbyProcessing
import pytest
import requests

from pbench.server import JSON, JSONOBJECT
from pbench.server.cache_manager import (
    CacheManager,
    CacheType,
    Inventory,
    TarballNotFound,
)
from pbench.server.database.models.datasets import Dataset, DatasetNotFound, Metadata
from pbench.server.database.models.users import User


class TestVisualize:
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
            dataset: str, user, expected_status: HTTPStatus
        ) -> requests.Response:
            try:
                dataset_id = Dataset.query(name=dataset).resource_id
            except DatasetNotFound:
                dataset_id = dataset  # Allow passing deliberately bad value
            headers = {"authorization": f"bearer {get_token_func(user)}"}
            response = client.get(
                f"{server_config.rest_uri}/datasets/{dataset_id}/visualize",
                headers=headers,
            )
            assert response.status_code == expected_status
            return response

        return query_api

    def mock_get_inventory(self, _dataset: str, target: str):
        return {
            "name": Path(target).name,
            "type": CacheType.FILE,
            "stream": Inventory(BytesIO(b"CSV_file_as_a_byte_stream"), None),
        }

    @staticmethod
    def mock_getvalue(_d: Dataset, _k: str, _u: Optional[User] = None) -> JSON:
        return "uperf"

    def test_get_no_dataset(self, query_get_as):
        """The dataset ID doesn't exist"""

        response = query_get_as("nonexistent-dataset", "drb", HTTPStatus.NOT_FOUND)
        assert response.json == {"message": "Dataset 'nonexistent-dataset' not found"}

    def test_dataset_not_cached(self, monkeypatch, query_get_as):
        """The dataset exists, but isn't in the cache manager"""

        def mock_inventory_not_found(self, d: str, _t: str) -> JSONOBJECT:
            raise TarballNotFound(d)

        monkeypatch.setattr(Metadata, "getvalue", self.mock_getvalue)
        monkeypatch.setattr(CacheManager, "get_inventory", mock_inventory_not_found)
        query_get_as("fio_2", "drb", HTTPStatus.INTERNAL_SERVER_ERROR)

    def test_unauthorized_access(self, query_get_as):
        """The dataset exists but isn't READABLE"""

        response = query_get_as("test", "drb", HTTPStatus.FORBIDDEN)
        assert response.json == {
            "message": "User drb is not authorized to READ a resource owned by test with private access"
        }

    def test_successful_get(self, query_get_as, monkeypatch):
        """Quisby processing succeeds"""

        def mock_extract_data(self, test_name, dataset_name, input_type, data) -> JSON:
            return {"status": "success", "json_data": "quisby_data"}

        monkeypatch.setattr(CacheManager, "get_inventory", self.mock_get_inventory)
        monkeypatch.setattr(Metadata, "getvalue", self.mock_getvalue)
        monkeypatch.setattr(QuisbyProcessing, "extract_data", mock_extract_data)

        response = query_get_as("uperf_1", "test", HTTPStatus.OK)
        assert response.json["status"] == "success"
        assert response.json["json_data"] == "quisby_data"

    def test_unsuccessful_get_with_incorrect_data(self, query_get_as, monkeypatch):
        """Quisby processing fails"""

        def mock_extract_data(self, test_name, dataset_name, input_type, data) -> JSON:
            return {"status": "failed", "exception": "Unsupported Media Type"}

        monkeypatch.setattr(CacheManager, "get_inventory", self.mock_get_inventory)
        monkeypatch.setattr(Metadata, "getvalue", self.mock_getvalue)
        monkeypatch.setattr(QuisbyProcessing, "extract_data", mock_extract_data)
        response = query_get_as("uperf_1", "test", HTTPStatus.INTERNAL_SERVER_ERROR)
        assert response.json["message"].startswith(
            "Internal Pbench Server Error: log reference "
        )

    def test_unsupported_benchmark(self, query_get_as, monkeypatch):
        """The benchmark name isn't supported"""

        extract_not_called = True

        def mock_extract_data(*args, **kwargs) -> JSON:
            nonlocal extract_not_called
            extract_not_called = False

        @staticmethod
        def mock_get_metadata(_d: Dataset, _k: str, _u: Optional[User] = None) -> JSON:
            return "hammerDB"

        monkeypatch.setattr(CacheManager, "get_inventory", self.mock_get_inventory)
        monkeypatch.setattr(Metadata, "getvalue", mock_get_metadata)
        monkeypatch.setattr(QuisbyProcessing, "extract_data", mock_extract_data)
        response = query_get_as("uperf_1", "test", HTTPStatus.BAD_REQUEST)
        assert response.json["message"] == "Unsupported Benchmark: HAMMERDB"
        assert extract_not_called
