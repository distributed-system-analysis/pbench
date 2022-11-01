import datetime
from http import HTTPStatus
from typing import Dict, List

import pytest
import requests

from pbench.server import JSON
from pbench.server.database.models.datasets import Dataset
from pbench.test.unit.server.conftest import admin_username, generate_token


class TestDatasetsDateRange:
    """
    Test the `datasets/daterange` API. We perform a variety of queries using a
    set of datasets provided by the `attach_dataset` fixture and the
    `more_datasets` fixture.
    """

    @pytest.fixture()
    def query_as(self, client, server_config, more_datasets, provide_metadata):
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
            payload: JSON, username: str, expected_status: HTTPStatus
        ) -> requests.Response:
            token = generate_token(
                username=username,
                pbench_client_roles=["ADMIN"] if username == admin_username else None,
            )
            response = client.get(
                f"{server_config.rest_uri}/datasets/daterange",
                headers={"authorization": f"bearer {token}"},
                query_string=payload,
            )
            assert response.status_code == expected_status
            return response

        return query_api

    def get_results(self, name_list: List[str]) -> Dict[str, datetime.datetime]:
        """
        Use a list of "expected results" to determine the earliest and the
        latest creation date of the set of datasets.

        Args:
            name_list: List of dataset names

        Returns:
            {"from": first_date, "to": last_date}
        """
        from_time = datetime.datetime.now(datetime.timezone.utc)
        to_time = datetime.datetime(
            year=1970, month=1, day=1, tzinfo=datetime.timezone.utc
        )
        for name in sorted(name_list):
            dataset = Dataset.query(name=name)
            to_time = max(dataset.created, to_time)
            from_time = min(dataset.created, from_time)
        return {"from": from_time.isoformat(), "to": to_time.isoformat()}

    @pytest.mark.parametrize(
        "login,query,results",
        [
            ("drb", {"owner": "drb"}, ["drb", "fio_1"]),
            ("drb", {"access": "public"}, ["drb", "fio_2"]),
            ("test_admin", {"owner": "drb"}, ["drb"]),
            ("drb", {}, ["drb", "fio_1", "fio_2"]),
            ("test", {}, ["test", "fio_1", "fio_2"]),
            ("test_admin", {}, ["drb", "test", "fio_1", "fio_2"]),
        ],
    )
    def test_dataset_daterange(self, query_as, login, query, results):
        """
        Test the operation of `datasets/daterange` against our set of test
        datasets.

        Args:
            query_as: A fixture to provide a helper that executes the API call
            login: The username as which to perform a query
            query: A JSON representation of the query parameters (these will be
                automatically supplemented with a metadata request term)
            results: A list of the dataset names we expect to be returned
        """
        result = query_as(query, login, HTTPStatus.OK)
        assert result.json == self.get_results(results)

    def test_get_unknown_keys(self, query_as):
        """
        Test case requesting non-existent query parameter keys.

        Args:
            query_as: Query helper fixture
        """
        response = query_as(
            {"plugh": "xyzzy", "passages": "twisty"},
            "drb",
            HTTPStatus.BAD_REQUEST,
        )
        assert response.json == {"message": "Unknown URL query keys: passages,plugh"}

    def test_get_repeat_keys(self, query_as):
        """
        Test case requesting repeated single-value query param keys.

        NOTE that the request package processes a list of values for a query
        parameter by repeating the key name with each value since the HTTP
        standard doesn't cover multiple values for a single key; so
        "name": ["one", "two"] will appear to the API as "?name=one&name=two".

        Args:
            query_as: Query helper fixture
        """
        response = query_as(
            {"owner": ["one", "two"]},
            "drb",
            HTTPStatus.BAD_REQUEST,
        )
        assert response.json == {"message": "Repeated URL query key 'owner'"}
