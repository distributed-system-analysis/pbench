import datetime
from http import HTTPStatus
import re

import pytest
import requests
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Query

from pbench.server import JSON, JSONARRAY, JSONOBJECT
from pbench.server.api.resources import APIAbort
from pbench.server.api.resources.datasets_list import DatasetsList, urlencode_json
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.test.unit.server import DRB_USER_ID

FLATTEN = re.compile(r"[\n\s]+")
LOG_SEQ = re.compile(r"Internal Pbench Server Error: log reference ([a-f0-9-]+)")


class TestUrlencodeJson:
    """Test operation of urlencode_json method."""

    def test_urlencode_json_empty(self):
        """Verify no harm, no foul."""
        encoding = urlencode_json({})
        assert encoding == "", f"Expected empty string, got {encoding!r}"

    def test_urlencode_json_no_metadata(self):
        """Verify normal operation."""
        encoding = urlencode_json(dict(a="one", b="two", c="three"))
        assert (
            encoding == "a=one&b=two&c=three"
        ), f"Unexpected encoding, got {encoding!r}"

    def test_urlencode_json(self):
        """Verify metadata list is comma separated."""
        encoding = urlencode_json(dict(a="one", metadata=["two", "four"], c="three"))
        assert (
            encoding == "a=one&c=three&metadata=two%2Cfour"
        ), f"Unexpected encoding, got {encoding!r}"


class TestDatasetsList:
    """Test the `datasets/list` API. We perform a variety of queries using a set
    of datasets provided by the `attach_dataset` fixture and the `more_datasets`
    fixture.
    """

    @pytest.fixture()
    def query_as(
        self, client, server_config, more_datasets, provide_metadata, get_token_func
    ):
        """Helper fixture to perform the API query and validate an expected
        return status.

        Args:
            client: Flask test API client fixture
            server_config: Pbench config fixture
            more_datasets: Dataset construction fixture
            provide_metadata: Dataset metadata fixture
            get_token_func: Pbench token fixture
        """

        def query_api(
            payload: JSON, username: str, expected_status: HTTPStatus
        ) -> requests.Response:
            """Encapsulate an HTTP GET operation with proper authentication, and
            check the return status.

            Args:
                payload:            Query parameter dict
                username:           Username to authenticate (None to skip
                                    authentication)
                expected_status:    Expected HTTP status

            Return:
                HTTP Response object
            """
            headers = None
            if username:
                token = get_token_func(username)
                headers = {"authorization": f"bearer {token}"}
            response = client.get(
                f"{server_config.rest_uri}/datasets/list",
                headers=headers,
                query_string=payload,
            )
            assert response.status_code == expected_status
            return response

        return query_api

    def get_results(self, name_list: list[str], query: JSON, server_config) -> JSON:
        """Translate a list of names into a list of expected results of the
        abbreviated form returned by `datasets/list`: name, controller, run_id,
        and metadata.

        Args:
            name_list: List of dataset names
            query: A JSON representation of the query parameters
            server_config: Pbench config fixture

        Returns:
            Paginated JSON object containing list of dataset values
        """
        results: list[JSON] = []
        offset = query.get("offset", 0)
        limit = query.get("limit")

        if limit:
            next_offset = offset + limit
            paginated_name_list = name_list[offset:next_offset]
            if next_offset >= len(name_list):
                next_url = ""
            else:
                query["offset"] = next_offset
                next_url = (
                    f"http://localhost{server_config.rest_uri}/datasets/list?"
                    + urlencode_json(query)
                )
        else:
            paginated_name_list = name_list[offset:]
            next_url = ""

        for name in sorted(paginated_name_list):
            dataset = Dataset.query(name=name)
            results.append(
                {
                    "name": dataset.name,
                    "resource_id": dataset.resource_id,
                    "metadata": {
                        "dataset.uploaded": datetime.datetime.isoformat(
                            dataset.uploaded
                        )
                    },
                }
            )
        return {"next_url": next_url, "results": results, "total": len(name_list)}

    def compare_results(
        self, result: JSONOBJECT, name_list: list[str], query: JSON, server_config
    ):
        """Compare two JSON results structures

        While pytest can reliably compare two dicts, or strings, when comparing
        lists we need to sort the elements. This helper compares each direct
        member of the results JSON but sorts the "results" list before doing
        the comparison to ensure consistency.
        """
        expected = self.get_results(name_list, query, server_config)
        for k, v in result.items():
            if k == "results":
                assert sorted(v, key=lambda d: d["resource_id"]) == sorted(
                    expected[k], key=lambda d: d["resource_id"]
                ), f"Actual {k}={v} doesn't match expected {expected[k]}"
            else:
                assert (
                    v == expected[k]
                ), f"Actual {k}={v!r} doesn't match expected {expected[k]!r}"

    @pytest.mark.parametrize(
        "login,query,results",
        [
            (None, {}, ["fio_1", "fio_2"]),
            (None, {"access": "public"}, ["fio_1", "fio_2"]),
            ("drb", {"name": "fio"}, ["fio_1", "fio_2"]),
            ("drb", {"name": "fio", "limit": 1}, ["fio_1", "fio_2"]),
            ("drb", {"name": "fio", "limit": 1, "offset": 2}, ["fio_1", "fio_2"]),
            ("drb", {"name": "fio", "offset": 1}, ["fio_1", "fio_2"]),
            ("drb", {"name": "fio", "offset": 2}, ["fio_1", "fio_2"]),
            ("drb", {"owner": "drb"}, ["drb", "fio_1"]),
            ("drb", {"name": "drb"}, ["drb"]),
            ("test", {"name": "drb"}, []),
            ("test_admin", {"name": "drb"}, ["drb"]),
            ("drb", {}, ["drb", "fio_1", "fio_2"]),
            (
                "test",
                {},
                ["test", "fio_1", "fio_2", "uperf_1", "uperf_2", "uperf_3", "uperf_4"],
            ),
            ("drb", {"owner": "drb"}, ["drb", "fio_1"]),
            ("drb", {"mine": "t"}, ["drb", "fio_1"]),
            ("drb", {"mine": "f"}, ["fio_2"]),
            (
                "test_admin",
                {},
                [
                    "drb",
                    "test",
                    "fio_1",
                    "fio_2",
                    "uperf_1",
                    "uperf_2",
                    "uperf_3",
                    "uperf_4",
                ],
            ),
            (
                "drb",
                {"start": "1978-06-25", "end": "2022-01-02"},
                ["drb", "fio_1", "fio_2"],
            ),
            ("drb", {"start": "2005-01-01"}, ["drb", "fio_2"]),
            (
                "test",
                {"end": "1980-01-01"},
                ["test", "fio_1", "uperf_1", "uperf_2", "uperf_3", "uperf_4"],
            ),
            ("drb", {"end": "1970-09-01"}, []),
            ("drb", {"filter": "dataset.access:public"}, ["fio_1", "fio_2"]),
            ("drb", {"filter": "dataset.name:fio_1"}, ["fio_1"]),
            (
                "test",
                {"filter": "^dataset.name:~fio,^dataset.name:uperf_1"},
                ["fio_1", "fio_2", "uperf_1"],
            ),
            (
                "test",
                {
                    "filter": "^dataset.name:~fio,^dataset.name:uperf_1,dataset.owner_id:3"
                },
                ["fio_1"],
            ),
        ],
    )
    def test_dataset_list(self, server_config, query_as, login, query, results):
        """Test `datasets/list` filters

        Args:
            server_config: The PbenchServerConfig object
            query_as: A fixture to provide a helper that executes the API call
            login: The username as which to perform a query
            query: A JSON representation of the query parameters (these will be
                automatically supplemented with a metadata request term)
            results: A list of the dataset names we expect to be returned
        """
        query.update({"metadata": ["dataset.uploaded"]})
        result = query_as(query, login, HTTPStatus.OK)
        self.compare_results(result.json, results, query, server_config)

    @pytest.mark.parametrize(
        "login,query,message",
        (
            (None, {"mine": True}, "'mine' filter requires authentication"),
            (None, {"mine": "no"}, "'mine' filter requires authentication"),
            (
                "drb",
                {"mine": "yes", "owner": "drb"},
                "'owner' and 'mine' filters cannot be used together",
            ),
            (
                "drb",
                {"mine": False, "owner": "test"},
                "'owner' and 'mine' filters cannot be used together",
            ),
            (
                "drb",
                {"mine": "no way!"},
                "Value 'no way!' (str) cannot be parsed as a boolean",
            ),
            ("drb", {"mine": 0}, "Value '0' (str) cannot be parsed as a boolean"),
        ),
    )
    def test_bad_mine(self, query_as, login, query, message):
        """Test the `mine` filter error conditions.

        Args:
            query_as: A fixture to provide a helper that executes the API call
            login: The username as which to perform a query
            query: A JSON representation of the query parameters
            message: The expected error message
        """
        result = query_as(query, login, HTTPStatus.BAD_REQUEST)
        assert result.json["message"] == message

    def test_mine_novalue(self, server_config, client, more_datasets, get_token_func):
        token = get_token_func("drb")
        headers = {"authorization": f"bearer {token}"}
        response = client.get(
            f"{server_config.rest_uri}/datasets/list?mine" "&metadata=dataset.uploaded",
            headers=headers,
        )
        assert response.status_code == HTTPStatus.OK
        self.compare_results(response.json, ["drb", "fio_1"], {}, server_config)

    @pytest.mark.parametrize(
        "login,query,results",
        [
            ("test", {"name": "drb"}, []),
            ("test", {"name": "test"}, ["test"]),
            (
                "test",
                {},
                ["test", "fio_1", "fio_2", "uperf_1", "uperf_2", "uperf_3", "uperf_4"],
            ),
        ],
    )
    def test_dataset_paged_list(self, query_as, login, query, results, server_config):
        """Test `datasets/list` with pagination limits.

        Args:
            query_as: A fixture to provide a helper that executes the API call
            login: The username as which to perform a query
            query: A JSON representation of the query parameters (these will be
                automatically supplemented with a metadata request term)
            results: A list of the dataset names we expect to be returned
        """
        query.update({"metadata": ["dataset.uploaded"], "limit": 5})
        result = query_as(query, login, HTTPStatus.OK)
        self.compare_results(result.json, results, query, server_config)

    def test_unauth_dataset_list(self, query_as):
        """Test `datasets/list` of private data for unauthenticated client

        Args:
            query_as: A fixture to provide a helper that executes the API call
            login: The username as which to perform a query
            query: A JSON representation of the query parameters (these will be
                automatically supplemented with a metadata request term)
            results: A list of the dataset names we expect to be returned
        """
        query_as({"access": "private"}, None, HTTPStatus.UNAUTHORIZED)

    def test_get_bad_keys(self, query_as):
        """Test case requesting non-existent metadata keys.

        Args:
            query_as: Query helper fixture
        """
        response = query_as(
            {"metadata": "xyzzy,plugh,dataset.owner,dataset.access"},
            "drb",
            HTTPStatus.BAD_REQUEST,
        )
        assert response.json == {
            "message": (
                "Unrecognized list values ['plugh', 'xyzzy'] given for"
                " parameter metadata; expected ['dataset', 'global', 'server',"
                " 'user']"
            )
        }

    def test_get_unknown_keys(self, query_as):
        """Test case requesting non-existent query parameter keys.

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
        """Test case requesting repeated single-value metadata keys.

        NOTE that the request package processes a list of values for a query
        parameter by repeating the key name with each value since the HTTP
        standard doesn't cover multiple values for a single key; so
        "name": ["one", "two"] will appear to the API as "?name=one&name=two".

        Args:
            query_as: Query helper fixture
        """
        response = query_as(
            {"name": ["one", "two"]},
            "drb",
            HTTPStatus.BAD_REQUEST,
        )
        assert response.json == {"message": "Repeated URL query key 'name'"}

    @pytest.mark.parametrize(
        "filters,expected",
        [
            (["dataset.name:fio"], "datasets.name = 'fio'"),
            (
                ["dataset.metalog.pbench.script:fio"],
                "dataset_metadata.key = 'metalog' "
                "AND dataset_metadata.value[['pbench', 'script']] = 'fio'",
            ),
            (
                ["user.d.f:1"],
                "dataset_metadata.key = 'user' AND dataset_metadata.value[['d', "
                "'f']] = '1' AND dataset_metadata.user_id = '3'",
            ),
            (
                ["dataset.name:~fio", "^global.x:1", "^user.y:~yes"],
                "(datasets.name LIKE '%' || 'fio' || '%') AND "
                "(dataset_metadata.key = 'global' AND "
                "dataset_metadata.value[['x']] = '1' OR dataset_metadata.key "
                "= 'user' AND ((dataset_metadata.value[['y']]) LIKE '%' || "
                "'yes' || '%') AND dataset_metadata.user_id = '3')",
            ),
            (
                ["dataset.uploaded:~2000"],
                "(CAST(datasets.uploaded AS VARCHAR) LIKE '%' || '2000' || '%')",
            ),
        ],
    )
    def test_filter_query(self, monkeypatch, client, filters, expected):
        """Test generation of Metadata value filters

        Use the filter_query method directly to verify SQL generation from sets
        of metadata filter expressions.
        """
        monkeypatch.setattr(
            "pbench.server.api.resources.datasets_list.Auth.get_current_user_id",
            lambda: DRB_USER_ID,
        )
        prefix = (
            "SELECT datasets.access, datasets.id, datasets.name, "
            "datasets.owner_id, datasets.resource_id, datasets.uploaded "
            "FROM datasets LEFT OUTER JOIN dataset_metadata ON datasets.id "
            "= dataset_metadata.dataset_ref WHERE "
        )
        query = DatasetsList.filter_query(
            filters, Database.db_session.query(Dataset).outerjoin(Metadata)
        )
        assert (
            FLATTEN.sub(
                " ",
                str(query.statement.compile(compile_kwargs={"literal_binds": True})),
            )
            == prefix + expected
        )

    def test_user_no_auth(self, monkeypatch, db_session):
        """Test the authorization error when a match against a key in the user
        namespace is attempted from an unauthenticated session.
        """
        monkeypatch.setattr(
            "pbench.server.api.resources.datasets_list.Auth.get_current_user_id",
            lambda: None,
        )
        with pytest.raises(APIAbort) as e:
            DatasetsList.filter_query(
                ["user.foo:1"], Database.db_session.query(Dataset).outerjoin(Metadata)
            )
        assert e.value.http_status == HTTPStatus.UNAUTHORIZED

    @pytest.mark.parametrize(
        "meta,error",
        [
            ("user.foo:1", HTTPStatus.UNAUTHORIZED),
            ("x.y:1", HTTPStatus.BAD_REQUEST),
            ("global.x=3", HTTPStatus.BAD_REQUEST),
            ("dataset.notright:10", HTTPStatus.BAD_REQUEST),
        ],
    )
    def test_filter_errors(self, monkeypatch, db_session, meta, error):
        """Test invalid filter expressions."""
        monkeypatch.setattr(
            "pbench.server.api.resources.datasets_list.Auth.get_current_user_id",
            lambda: None,
        )
        with pytest.raises(APIAbort) as e:
            DatasetsList.filter_query(
                [meta], Database.db_session.query(Dataset).outerjoin(Metadata)
            )
        assert e.value.http_status == error

    @pytest.mark.parametrize(
        "exception,error",
        (
            (Exception("test"), "Unexpected SQL exception: test"),
            (
                ProgrammingError("stmt", [], "orig"),
                "Constructed SQL for {} isn't executable",
            ),
        ),
    )
    def test_pagination_error(self, caplog, monkeypatch, query_as, exception, error):
        """Test that query problems during pagination are reported as server
        internal errors.
        """

        def do_error(
            self, query: Query, json: JSONOBJECT, url: str
        ) -> tuple[JSONARRAY, JSONOBJECT]:
            raise exception

        monkeypatch.setattr(DatasetsList, "get_paginated_obj", do_error)
        response = query_as({}, "drb", HTTPStatus.INTERNAL_SERVER_ERROR)
        message = response.json["message"]
        match = LOG_SEQ.match(message)
        key = match.group(1)
        assert match and key, "Error response {message!r} is not an internal error"
        for m in caplog.messages:
            if key in m:
                assert error in m
                break
