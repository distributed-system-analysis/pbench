import datetime
from http import HTTPStatus
import pytest
import requests
from typing import List

from freezegun.api import freeze_time

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import JSON
from pbench.server.database.models.datasets import Dataset


class TestDatasetsList:
    """
    Test the `datasets/list` API. We perform a variety of queries using a set
    of datasets:

        Owner   Access  Date        Name
        ------- ------- ----------- ---------
        drb     private 2020-02-15  drb
        test    private 2002-06-16  test
        drb     public  2020-02-15  fio_1
        test    public  2002-06-16  fio_2

    Two of these are provided by the external `attach_dataset` fixture, the
    others by the local `more_datasets` fixture.
    """

    @pytest.fixture()
    def more_datasets(
        self, client, server_config, create_drb_user, create_admin_user, attach_dataset
    ):
        """
        Supplement the conftest.py "attach_dataset" fixture with a few more
        datasets so we can practice various queries.

        Args:
            client: Provide a Flask API client
            server_config: Provide a Pbench server configuration
            create_drb_user: Create the "drb" user
            create_admin_user: Create the "test_admin" user
            attach_dataset: Provide some datasets
        """
        with freeze_time("1978-06-26 08:00:00"):
            Dataset(
                owner="drb",
                created=datetime.datetime(2020, 2, 15),
                uploaded=datetime.datetime(2022, 1, 1),
                controller="node1",
                name="fio_1",
                access="public",
                md5="random_md5_string3",
            ).add()
            Dataset(
                owner="test",
                created=datetime.datetime(2002, 5, 16),
                controller="node2",
                name="fio_2",
                access="public",
                md5="random_md5_string4",
            ).add()

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
            token = self.token(client, server_config, username)
            response = client.get(
                f"{server_config.rest_uri}/datasets/list",
                headers={"authorization": f"bearer {token}"},
                query_string=payload,
            )
            assert response.status_code == expected_status
            return response

        return query_api

    def token(self, client, config: PbenchServerConfig, user: str) -> str:
        response = client.post(
            f"{config.rest_uri}/login", json={"username": user, "password": "12345"},
        )
        assert response.status_code == HTTPStatus.OK
        data = response.json
        assert data["auth_token"]
        return data["auth_token"]

    def get_results(self, name_list: List[str]) -> JSON:
        """
        Translate a list of names into a list of expected results of the
        abbreviated form returned by `datasets/list`: name, controller,
        run_id, and metadata.

        Args:
            name_list: List of dataset names

        Returns:
            JSON list of dataset values
        """
        list: List[JSON] = []
        for name in sorted(name_list):
            dataset = Dataset.query(name=name)
            list.append(
                {
                    "name": dataset.name,
                    "controller": dataset.controller,
                    "run_id": dataset.md5,
                    "metadata": {
                        "dataset.created": f"{dataset.created:%Y-%m-%d:%H:%M}"
                    },
                }
            )
        return list

    @pytest.mark.parametrize(
        "login,query,results",
        [
            ("drb", {"name": "fio"}, ["fio_1", "fio_2"]),
            ("drb", {"owner": "drb"}, ["drb", "fio_1"]),
            ("drb", {"controller": "foobar"}, []),
            ("drb", {"name": "drb"}, ["drb"]),
            ("test", {"name": "drb"}, []),
            ("test_admin", {"name": "drb"}, ["drb"]),
            ("drb", {"controller": "node"}, ["drb"]),
            ("drb", {}, ["drb", "fio_1", "fio_2"]),
            ("test", {}, ["test", "fio_1", "fio_2"]),
            ("test_admin", {}, ["drb", "test", "fio_1", "fio_2"]),
            ("drb", {"start": "2000-01-01", "end": "2005-12-31"}, ["fio_2"]),
            ("drb", {"start": "2005-01-01"}, ["drb", "fio_1"]),
            ("drb", {"end": "2020-09-01"}, ["drb", "fio_1", "fio_2"]),
            ("drb", {"end": "1970-09-01"}, []),
        ],
    )
    def test_dataset_list(self, query_as, login, query, results):
        """
        Test the operation of `datasets/list` against our set of test
        datasets.

        Args:
            query_as: A fixture to provide a helper that executes the API call
            login: The username as which to perform a query
            query: A JSON representation of the query parameters (these will be
                automatically supplemented with a metadata request term)
            results: A list of the dataset names we expect to be returned
        """
        query.update({"metadata": ["dataset.created"]})
        result = query_as(query, login, HTTPStatus.OK)
        assert result.json == self.get_results(results)

    def test_get_bad_keys(self, query_as):
        """
        Test case requesting non-existent metadata keys.

        Args:
            query_as: Query helper fixture
        """
        response = query_as(
            {"metadata": ["xyzzy", "plugh", "dataset.owner", "dataset.access"]},
            "drb",
            HTTPStatus.BAD_REQUEST,
        )
        assert response.json == {
            "message": "Unrecognized list values ['plugh', 'xyzzy'] given for parameter metadata; expected ['dashboard.*', 'dataset.access', 'dataset.created', 'dataset.owner', 'dataset.uploaded', 'server.deletion', 'user.*']"
        }
