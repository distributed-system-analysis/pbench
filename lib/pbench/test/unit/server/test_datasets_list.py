import datetime
from http import HTTPStatus
import re
from typing import Optional

import pytest
import requests
from sqlalchemy import and_, desc
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import aliased, Query

from pbench.server import JSON, JSONARRAY, JSONOBJECT
from pbench.server.api.resources import APIAbort
from pbench.server.api.resources.datasets_list import DatasetsList, urlencode_json
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.database.models.users import User
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

    def filter_setup(self, auth_id: Optional[str]):
        """Set up SQLAlchemy for filter_query unit tests.

        This generates the basic query to allow generating
        filter expressions.
        """
        aliases = {
            Metadata.METALOG: aliased(Metadata),
            Metadata.SERVER: aliased(Metadata),
            Metadata.GLOBAL: aliased(Metadata),
            Metadata.USER: aliased(Metadata),
        }
        query = Database.db_session.query(Dataset)
        for key, table in aliases.items():
            terms = [table.dataset_ref == Dataset.id, table.key == key]
            if key == Metadata.USER:
                if not auth_id:
                    continue
                terms.append(table.user_ref == auth_id)
            query = query.outerjoin(table, and_(*terms))
        return aliases, query

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
                f"{server_config.rest_uri}/datasets",
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
                    f"http://localhost{server_config.rest_uri}/datasets?"
                    + urlencode_json(query)
                )
        else:
            paginated_name_list = name_list[offset:]
            next_url = ""

        for name in paginated_name_list:
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
                assert (
                    v == expected[k]
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
            ("drb", {"mine": "t", "access": "private"}, ["drb"]),
            ("drb", {"mine": "t", "access": "public"}, ["fio_1"]),
            ("drb", {"mine": "f", "access": "private"}, []),
            ("drb", {"mine": "f", "access": "public"}, ["fio_2"]),
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
            f"{server_config.rest_uri}/datasets?mine&metadata=dataset.uploaded",
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
            server_config: The PbenchServerConfig object
        """
        query.update({"metadata": ["dataset.uploaded"], "limit": 5})
        result = query_as(query, login, HTTPStatus.OK)
        self.compare_results(result.json, results, query, server_config)

    def test_unauth_dataset_list(self, query_as):
        """Test `datasets/list` of private data for unauthenticated client

        Args:
            query_as: A fixture to provide a helper that executes the API call
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

    def test_get_key_errors(self, query_as):
        """Test case reporting key errors

        Args:
            query_as: Query helper fixture
        """
        fio_1 = Dataset.query(name="fio_1")
        fio_2 = Dataset.query(name="fio_2")
        Metadata.setvalue(dataset=fio_1, key="global.test", value="ABC")
        Metadata.setvalue(dataset=fio_2, key="global.test.foo", value="ABC")
        response = query_as(
            {"metadata": "global.test.foo"},
            "drb",
            HTTPStatus.OK,
        )
        assert response.json == {
            "next_url": "",
            "results": [
                {
                    "metadata": {"global.test.foo": None},
                    "name": "drb",
                    "resource_id": "random_md5_string1",
                },
                {
                    "metadata": {"global.test.foo": None},
                    "name": "fio_1",
                    "resource_id": "random_md5_string3",
                },
                {
                    "metadata": {"global.test.foo": "ABC"},
                    "name": "fio_2",
                    "resource_id": "random_md5_string4",
                },
            ],
            "total": 3,
        }

    def test_use_funk_metalog_keys(self, query_as):
        """Test funky metadata.log keys

        Normally we constrain metadata keys to lowercase alphanumeric strings.
        Traditional Pbench Agent `metadata.log` files contain keys constructed
        from benchmark iteration values that can contain mixed case and symbol
        characters. We allow these keys to be filtered and retrieved, but not
        created, so test that we can filter on a funky key value and return
        the key.

        Args:
            query_as: Query helper fixture
        """
        fio_1 = Dataset.query(name="fio_1")
        Metadata.create(
            dataset=fio_1,
            key=Metadata.METALOG,
            value={
                "pbench": {
                    "date": "2020-02-15T00:00:00",
                    "config": "test1",
                    "script": "unit-test",
                    "name": "fio_1",
                },
                "iterations/fooBar=10-what_else@weird": {
                    "iteration_name": "fooBar=10-what_else@weird"
                },
                "run": {"controller": "node1.example.com"},
            },
        )
        response = query_as(
            {
                "metadata": "dataset.metalog.iterations/fooBar=10-what_else@weird",
                "filter": "dataset.metalog.iterations/fooBar=10-what_else@weird.iteration_name:~10",
            },
            "drb",
            HTTPStatus.OK,
        )
        assert response.json == {
            "next_url": "",
            "results": [
                {
                    "metadata": {
                        "dataset.metalog.iterations/fooBar=10-what_else@weird": {
                            "iteration_name": "fooBar=10-what_else@weird"
                        }
                    },
                    "name": "fio_1",
                    "resource_id": "random_md5_string3",
                }
            ],
            "total": 1,
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
            (["dataset.name:=fio"], "datasets.name = 'fio'"),
            (
                ["dataset.uploaded:>2023-01-01:date"],
                "datasets.uploaded > '2023-01-01 00:00:00'",
            ),
            (
                ["dataset.uploaded:!=2023-01-01:date"],
                "datasets.uploaded != '2023-01-01 00:00:00'",
            ),
            (
                ["server.deletion:<2023-05-01:date"],
                "CAST(dataset_metadata_2.value[['deletion']] AS DATETIME) < '2023-05-01 00:00:00'",
            ),
            (
                ["'dataset.metalog.pbench.script':='fio'"],
                "CAST(dataset_metadata_1.value[['pbench', 'script']] AS VARCHAR) = 'fio'",
            ),
            (
                ["'dataset.metalog.pbench.script':!=fio"],
                "CAST(dataset_metadata_1.value[['pbench', 'script']] AS VARCHAR) != 'fio'",
            ),
            (
                ["dataset.metalog.run.date:~fio"],
                "(CAST(dataset_metadata_1.value[['run', 'date']] AS VARCHAR) LIKE '%' || 'fio' || '%')",
            ),
            (
                ["global.something.integer:<1:int"],
                "CAST(dataset_metadata_3.value[['something', 'integer']] AS INTEGER) < 1",
            ),
            (
                ["global.something.integer:>2:int"],
                "CAST(dataset_metadata_3.value[['something', 'integer']] AS INTEGER) > 2",
            ),
            (
                ["global.something.integer:<=1:int"],
                "CAST(dataset_metadata_3.value[['something', 'integer']] AS INTEGER) <= 1",
            ),
            (
                ["global.something.integer:>=2:int"],
                "CAST(dataset_metadata_3.value[['something', 'integer']] AS INTEGER) >= 2",
            ),
            (
                ["global.something.boolean:t:bool"],
                "CAST(dataset_metadata_3.value[['something', 'boolean']] AS BOOLEAN) = true",
            ),
            (
                ["user.d.f:1"],
                "CAST(dataset_metadata_4.value[['d', 'f']] AS VARCHAR) = '1'",
            ),
            (
                ["dataset.name:~fio", "^'global.x':1", "^user.y:~yes"],
                "(datasets.name LIKE '%' || 'fio' || '%') AND (CAST(dataset_metadata_3.value[['x']] AS VARCHAR) = '1' OR (CAST(dataset_metadata_4.value[['y']] AS VARCHAR) LIKE '%' || 'yes' || '%'))",
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
            "SELECT datasets.access, datasets.id, datasets.name, datasets.owner_id, datasets.resource_id, datasets.uploaded "
            "FROM datasets LEFT OUTER JOIN dataset_metadata AS dataset_metadata_1 ON dataset_metadata_1.dataset_ref = datasets.id AND dataset_metadata_1.key = 'metalog' "
            "LEFT OUTER JOIN dataset_metadata AS dataset_metadata_2 ON dataset_metadata_2.dataset_ref = datasets.id AND dataset_metadata_2.key = 'server' "
            "LEFT OUTER JOIN dataset_metadata AS dataset_metadata_3 ON dataset_metadata_3.dataset_ref = datasets.id AND dataset_metadata_3.key = 'global' "
            "LEFT OUTER JOIN dataset_metadata AS dataset_metadata_4 ON dataset_metadata_4.dataset_ref = datasets.id AND dataset_metadata_4.key = 'user' AND dataset_metadata_4.user_ref = '3' WHERE "
        )
        aliases, query = self.filter_setup(DRB_USER_ID)
        query = DatasetsList.filter_query(filters, aliases, query)
        assert (
            FLATTEN.sub(
                " ",
                str(query.statement.compile(compile_kwargs={"literal_binds": True})),
            )
            == prefix + expected
        )

    @pytest.mark.parametrize(
        "filters,expected",
        [
            (["dataset.name:fio"], "datasets.name = 'fio'"),
            (
                ["dataset.metalog.pbench.script:fio"],
                "CAST(dataset_metadata_1.value[['pbench', 'script']] AS VARCHAR) = 'fio'",
            ),
            (
                ["dataset.name:~fio", "^global.x:1"],
                "(datasets.name LIKE '%' || 'fio' || '%') AND CAST(dataset_metadata_3.value[['x']] AS VARCHAR) = '1'",
            ),
            (
                ["dataset.uploaded:~2000"],
                "(CAST(datasets.uploaded AS VARCHAR) LIKE '%' || '2000' || '%')",
            ),
        ],
    )
    def test_filter_query_noauth(self, monkeypatch, client, filters, expected):
        """Test generation of Metadata value filters

        Use the filter_query method directly to verify SQL generation from sets
        of metadata filter expressions.
        """
        monkeypatch.setattr(
            "pbench.server.api.resources.datasets_list.Auth.get_current_user_id",
            lambda: None,
        )
        prefix = (
            "SELECT datasets.access, datasets.id, datasets.name, datasets.owner_id, datasets.resource_id, datasets.uploaded "
            "FROM datasets LEFT OUTER JOIN dataset_metadata AS dataset_metadata_1 ON dataset_metadata_1.dataset_ref = datasets.id AND dataset_metadata_1.key = 'metalog' "
            "LEFT OUTER JOIN dataset_metadata AS dataset_metadata_2 ON dataset_metadata_2.dataset_ref = datasets.id AND dataset_metadata_2.key = 'server' "
            "LEFT OUTER JOIN dataset_metadata AS dataset_metadata_3 ON dataset_metadata_3.dataset_ref = datasets.id AND dataset_metadata_3.key = 'global' WHERE "
        )
        aliases, query = self.filter_setup(None)
        query = DatasetsList.filter_query(filters, aliases, query)
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
        aliases, query = self.filter_setup(None)
        with pytest.raises(APIAbort) as e:
            DatasetsList.filter_query(["user.foo:1"], aliases, query)
        assert e.value.http_status == HTTPStatus.UNAUTHORIZED

    @pytest.mark.parametrize(
        "meta,error,message",
        [
            (
                "user.foo:1",
                HTTPStatus.UNAUTHORIZED,
                "Metadata key user.foo cannot be used by an unauthenticated client",
            ),
            ("x.y:1", HTTPStatus.BAD_REQUEST, "Metadata key 'x.y' is not supported"),
            (
                "global.x=3",
                HTTPStatus.BAD_REQUEST,
                "Missing ':' terminator in 'global.x=3'",
            ),
            (
                "'global.x'",
                HTTPStatus.BAD_REQUEST,
                "Missing ':' terminator in 'global.x'",
            ),
            (
                "dataset.x':v",
                HTTPStatus.BAD_REQUEST,
                'Metadata key "dataset.x\'" is not supported',
            ),
            (
                "dataset.notright:10",
                HTTPStatus.BAD_REQUEST,
                "Metadata key 'dataset.notright' is not supported",
            ),
            (
                "'dataset.name:foo",
                HTTPStatus.BAD_REQUEST,
                'Bad quote termination in "\'dataset.name:foo"',
            ),
            (
                "dataset.name:'foo",
                HTTPStatus.BAD_REQUEST,
                'Bad quote termination in "dataset.name:\'foo"',
            ),
            (
                "server.deletion:<2023-05-01:time",
                HTTPStatus.BAD_REQUEST,
                "The filter type 'time' must be one of bool,date,int,str",
            ),
            (
                "server.deletion:2023-05-01:date:",
                HTTPStatus.BAD_REQUEST,
                "The filter type 'date:' must be one of bool,date,int,str",
            ),
        ],
    )
    def test_filter_errors(self, monkeypatch, client, meta, error, message):
        """Test invalid filter expressions."""
        monkeypatch.setattr(
            "pbench.server.api.resources.datasets_list.Auth.get_current_user_id",
            lambda: None,
        )
        aliases, query = self.filter_setup(None)
        with pytest.raises(APIAbort) as e:
            DatasetsList.filter_query([meta], aliases, query)
        assert e.value.http_status == error
        assert str(e.value) == message

    @pytest.mark.parametrize(
        "query,results",
        [
            ("global.legacy:t:bool", ["drb"]),
            ("global.legacy:>2:int", ["fio_2"]),
            ("global.legacy:>2023-05-01:date", []),
        ],
    )
    def test_mismatched_json_cast(self, query_as, server_config, query, results):
        """Verify DB engine behavior for mismatched metadata casts.

        Verify that a typed filter ignores datasets where the metadata key
        type isn't compatible with the required cast.
        """
        drb = Dataset.query(name="drb")
        fio_1 = Dataset.query(name="fio_1")
        fio_2 = Dataset.query(name="fio_2")

        Metadata.setvalue(dataset=drb, key="global.legacy", value=True)
        Metadata.setvalue(dataset=fio_1, key="global.legacy.server", value="ABC")
        Metadata.setvalue(dataset=fio_2, key="global.legacy", value=4)

        response = query_as(
            {"filter": query, "metadata": ["dataset.uploaded"]},
            "drb",
            HTTPStatus.OK,
        )
        self.compare_results(response.json, results, {}, server_config)

    @pytest.mark.parametrize(
        "query,message",
        [
            (
                "dataset.name:t:bool",
                "Filter of type 'bool' is not compatible with key 'dataset.name'",
            ),
            (
                "dataset.uploaded:>2:int",
                "Filter of type 'int' is not compatible with key 'dataset.uploaded'",
            ),
        ],
    )
    def test_mismatched_dataset_cast(self, query_as, server_config, query, message):
        """Verify DB engine behavior for mismatched metadata casts.

        Verify that a typed filter generates an error when it targets a primary
        dataset key with an incompatible type.
        """
        response = query_as(
            {"filter": query, "metadata": ["dataset.uploaded"]},
            "drb",
            HTTPStatus.BAD_REQUEST,
        )
        assert response.json["message"] == message

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

    def test_key_summary(self, query_as):
        """Test keyspace summary.

        With the `keysummary` query parameter, /datasets returns an aggregation
        of defined metadata key namespaces for the selected datasets.

        We add a few metadata kays to the ones provided by the fixture to show
        aggregation across multiple selected datasets. Note that without filter
        criteria, the query here should return drb's "drb" and "fio_1" datasets
        and test's public "fio_2" dataset.
        """
        drb = Dataset.query(name="drb")
        fio_1 = Dataset.query(name="fio_1")

        # Make sure we aggregate distinct namespaces across the three visible
        # datasets by setting some varied keys. We leave fio_2 "pristine" to
        # prove that the aggregator doesn't fail when we find no metadata for
        # a dataset. We deliberately create the conflicting "global.legacy"
        # and "global.legacy.server" to show that the conflict doesn't cause
        # a problem.
        Metadata.setvalue(dataset=drb, key="global.legacy", value="Truish")
        Metadata.setvalue(dataset=fio_1, key="server.origin", value="SAT")
        Metadata.setvalue(dataset=fio_1, key="global.legacy.server", value="ABC")
        response = query_as({"keysummary": "true"}, "drb", HTTPStatus.OK)
        assert response.json == {
            "keys": {
                "dataset": {
                    "access": None,
                    "id": None,
                    "metalog": {
                        "pbench": {
                            "config": None,
                            "date": None,
                            "name": None,
                            "script": None,
                        },
                        "run": {"controller": None},
                    },
                    "name": None,
                    "owner_id": None,
                    "resource_id": None,
                    "uploaded": None,
                },
                "global": {"contact": None, "legacy": {"server": None}},
                "server": {
                    "deletion": None,
                    "index-map": {
                        "unit-test.v5.result-data-sample.2020-08": None,
                        "unit-test.v6.run-data.2020-08": None,
                        "unit-test.v6.run-toc.2020-05": None,
                    },
                    "origin": None,
                },
            }
        }

    def get_daterange_results(
        self, name_list: list[str]
    ) -> dict[str, datetime.datetime]:
        """
        Use a list of "expected results" to determine the earliest and the
        latest creation date of the set of datasets.

        Args:
            name_list: List of dataset names

        Returns:
            {"from": first_date, "to": last_date}

            or

            {} if the list is empty
        """
        if not name_list:
            return {}
        to_time = max(Dataset.query(name=n).uploaded for n in name_list)
        from_time = min(Dataset.query(name=n).uploaded for n in name_list)
        return {"from": from_time.isoformat(), "to": to_time.isoformat()}

    @pytest.mark.parametrize(
        "login,query,results",
        [
            ("drb", {"owner": "drb"}, ["drb", "fio_1"]),
            ("drb", {"mine": "true"}, ["drb", "fio_1"]),
            ("drb", {"access": "public"}, ["fio_1", "fio_2"]),
            ("drb", {"name": "noname"}, []),
            ("test_admin", {"owner": "drb"}, ["drb", "fio_1"]),
            ("drb", {}, ["drb", "fio_1", "fio_2"]),
            (
                "test",
                {},
                ["test", "fio_1", "fio_2", "uperf_1", "uperf_2", "uperf_3", "uperf_4"],
            ),
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
        ],
    )
    def test_dataset_daterange(self, query_as, login, query, results):
        """
        Test the operation of `GET datasets?daterange` against our set of test
        datasets.

        Args:
            query_as: A fixture to provide a helper that executes the API call
            login: The username as which to perform a query
            query: A JSON representation of the query parameters (these will be
                automatically supplemented with the "daterange" parameter)
            results: A list of the dataset names we expect to be returned
        """
        query["daterange"] = "true"
        result = query_as(query, login, HTTPStatus.OK)
        assert result.json == self.get_daterange_results(results)

    def test_key_and_dates(self, query_as):
        """Test keyspace summary in combination with date range

        This tests that we can use "keysummary" and "daterange" together.
        """
        response = query_as(
            {"keysummary": "true", "daterange": "true"}, "drb", HTTPStatus.OK
        )
        assert response.json == {
            "from": "1978-06-26T08:00:00+00:00",
            "to": "2022-01-01T00:00:00+00:00",
            "keys": {
                "dataset": {
                    "access": None,
                    "id": None,
                    "metalog": {
                        "pbench": {
                            "config": None,
                            "date": None,
                            "name": None,
                            "script": None,
                        },
                        "run": {"controller": None},
                    },
                    "name": None,
                    "owner_id": None,
                    "resource_id": None,
                    "uploaded": None,
                },
                "global": {"contact": None},
                "server": {
                    "deletion": None,
                    "index-map": {
                        "unit-test.v5.result-data-sample.2020-08": None,
                        "unit-test.v6.run-data.2020-08": None,
                        "unit-test.v6.run-toc.2020-05": None,
                    },
                },
            },
        }

    @pytest.mark.parametrize(
        "sort,results",
        [
            (
                # Simple sort by name
                "dataset.name",
                ["fio_1", "fio_2", "test", "uperf_1", "uperf_2", "uperf_3", "uperf_4"],
            ),
            (
                # Simple sort by name with explicit "ascending" order
                "dataset.name:asc",
                ["fio_1", "fio_2", "test", "uperf_1", "uperf_2", "uperf_3", "uperf_4"],
            ),
            (
                # Simple sort by name with "descending" order
                "dataset.name:desc",
                ["uperf_4", "uperf_3", "uperf_2", "uperf_1", "test", "fio_2", "fio_1"],
            ),
            (
                # Sort by date timestamp
                "dataset.uploaded",
                ["test", "fio_1", "uperf_1", "uperf_2", "uperf_3", "uperf_4", "fio_2"],
            ),
            (
                # Sort by date timestamp with descending order
                "dataset.uploaded:desc",
                ["fio_2", "uperf_4", "uperf_3", "uperf_2", "uperf_1", "fio_1", "test"],
            ),
            (
                # Sort by a "dataset.metalog" value
                "dataset.metalog.run.controller",
                ["test", "fio_1", "fio_2", "uperf_1", "uperf_2", "uperf_3", "uperf_4"],
            ),
            (
                # Sort by a general global metadata value in descending order
                "global.test.sequence:desc",
                ["fio_1", "fio_2", "test", "uperf_1", "uperf_2", "uperf_3", "uperf_4"],
            ),
            (
                # Sprt by a general global metadata value in ascending order
                "global.test.sequence",
                ["uperf_4", "uperf_3", "uperf_2", "uperf_1", "test", "fio_2", "fio_1"],
            ),
            (
                # Sort two keys across distinct metadata namespaces asc/desc
                "user.test.odd,global.test.sequence:desc",
                ["fio_1", "test", "uperf_2", "uperf_4", "fio_2", "uperf_1", "uperf_3"],
            ),
            (
                # Sort two keys across distinct metadata namespaces desc/desc
                "user.test.odd:desc,dataset.name:desc",
                ["uperf_3", "uperf_1", "fio_2", "uperf_4", "uperf_2", "test", "fio_1"],
            ),
            (
                # Sort by a JSON sub-object containing two keys ascending
                "global.test",
                ["uperf_4", "uperf_3", "uperf_2", "uperf_1", "test", "fio_2", "fio_1"],
            ),
            (
                # Sort by a JSON sub-object containing two keys descending
                "global.test:desc",
                ["fio_1", "fio_2", "test", "uperf_1", "uperf_2", "uperf_3", "uperf_4"],
            ),
        ],
    )
    def test_dataset_sort(self, server_config, query_as, sort, results):
        """Test `datasets/list?sort`

        We want a couple of consistent values sequences to play with. We can
        use the dataset.name and dataset.resource_id fields, but we want to
        cross Metadata namespaces, so add "global" and "user" keys we can
        order.

        Args:
            server_config: The PbenchServerConfig object
            query_as: A fixture to provide a helper that executes the API call
            sort: A JSON representation of the sort query parameter value
            results: A list of the dataset names we expect to be returned
        """

        # Assign "sequence numbers" in the inverse order of name
        test = User.query(username="test")
        all = Database.db_session.query(Dataset).order_by(desc(Dataset.name)).all()
        for i, d in enumerate(all):
            odd = i & 1
            Metadata.setvalue(d, "global.test.sequence", i)
            Metadata.setvalue(d, "global.test.mcguffin", 100 - i)
            Metadata.setvalue(d, "user.test.odd", odd, user=test)
        query = {"sort": sort, "metadata": ["dataset.uploaded"]}
        result = query_as(query, "test", HTTPStatus.OK)
        self.compare_results(result.json, results, query, server_config)

    @pytest.mark.parametrize(
        "sort,message",
        [
            (
                # Specify a sort by a Dataset table column that doesn't exist
                "dataset.noname",
                "Metadata key 'dataset.noname' is not supported",
            ),
            (
                # Specify a sort using an undefined order keyword
                "dataset.name:backwards",
                "The sort order 'backwards' for key 'dataset.name' must be 'asc' or 'desc'",
            ),
            (
                # Specify a sort using bad sort order syntax
                "dataset.name:desc:",
                "The sort order 'desc:' for key 'dataset.name' must be 'asc' or 'desc'",
            ),
            (
                # Specify a sort using a bad metadata namespace
                "xyzzy.uploaded",
                "Metadata key 'xyzzy.uploaded' is not supported",
            ),
        ],
    )
    def test_dataset_sort_errors(self, server_config, query_as, sort, message):
        """Test `datasets/list?sort` error cases

        Args:
            server_config: The PbenchServerConfig object
            query_as: A fixture to provide a helper that executes the API call
            sort: A JSON representation of the sort query parameter value
            message: The expected error message
        """
        query = {"sort": sort}
        result = query_as(query, "test", HTTPStatus.BAD_REQUEST)
        assert result.json["message"] == message
