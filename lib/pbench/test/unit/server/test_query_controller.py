import pytest
import re
import requests

from pbench.server.api.resources.query_apis import get_es_url, get_index_prefix


@pytest.fixture
def query_helper(client, server_config, requests_mock):
    """
    query_helper Help controller queries that want to interact with a mocked
    Elasticsearch service.

    This is a fixture which exposes a function of the same name that can be
    used to set up and validate a mocked Elasticsearch query with a JSON
    payload and an expected status.

    Parameters to the mocked Elasticsearch POST are passed as keyword
    parameters: these can be any of the parameters supported by the
    request_mock post method. The most common are 'json' for the JSON
    response payload, and 'exc' to throw an exception.

    :return: the response object for further checking
    """

    def query_helper(payload, expected_index, expected_status, server_config, **kwargs):
        es_url = get_es_url(server_config)
        requests_mock.post(re.compile(f"{es_url}"), **kwargs)
        response = client.post(
            f"{server_config.rest_uri}/controllers/list", json=payload
        )
        assert requests_mock.last_request.url == (
            es_url + expected_index + "/_search?ignore_unavailable=true"
        )
        assert response.status_code == expected_status
        return response

    return query_helper


class TestQueryControllers:
    """
    Unit testing for resources/QueryControllers class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    def build_index(self, server_config, dates):
        """
        build_index Build the index list for query

        Args:
            dates (iterable): list of date strings
        """
        prefix = get_index_prefix(server_config)
        idx = prefix + ".v6.run-data."
        index = "/"
        for d in dates:
            index += f"{idx}{d},"
        return index

    def test_missing_json_object(self, client, server_config):
        """
        test_missing_json_object Test behavior when no JSON payload is given
        """
        response = client.post(f"{server_config.rest_uri}/controllers/list")
        assert response.status_code == 400
        assert (
            response.json.get("message") == "QueryControllers: Missing request payload"
        )

    @pytest.mark.parametrize(
        "keys",
        (
            {"user": "x"},
            {"start": "2020"},
            {"end": "2020"},
            {"user": "x", "start": "2020"},
            {"user": "x", "end": "2020"},
            {"start": "2020", "end": "2020"},
        ),
    )
    def test_missing_keys(self, client, server_config, keys):
        """
        test_missing_keys Test behavior when JSON payload does not contain
        all required keys.

        Note that "user", "prefix", "start", and "end" are all required;
        however, Pbench will silently ignore any additional keys that are
        specified.
       """
        response = client.post(f"{server_config.rest_uri}/controllers/list", json=keys)
        assert response.status_code == 400
        missing = [k for k in ("user", "start", "end") if k not in keys]
        assert (
            response.json.get("message")
            == f"QueryControllers: Missing request data: {','.join(missing)}"
        )

    def test_bad_dates(self, client, server_config):
        """
        test_bad_dates Test behavior when a bad date string is given
        """
        response = client.post(
            f"{server_config.rest_uri}/controllers/list",
            json={
                "user": "drb",
                "prefix": "drb-",
                "start": "2020-15",
                "end": "2020-19",
            },
        )
        assert response.status_code == 400
        assert (
            response.json.get("message")
            == "QueryControllers: Invalid start or end time string"
        )

    def test_query(self, client, server_config, query_helper):
        """
        test_query Check the construction of Elasticsearch query URI
        and filtering of the response body.
        """
        json = {
            "user": "drb",
            "start": "2020-08",
            "end": "2020-10",
        }
        response_payload = {
            "took": 1,
            "timed_out": False,
            "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "max_score": None,
                "hits": [],
            },
            "aggregations": {
                "controllers": {
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                    "buckets": [
                        {
                            "key": "unittest-controller1",
                            "doc_count": 2,
                            "runs": {
                                "value": 1.59847315581e12,
                                "value_as_string": "2020-08-26T20:19:15.810Z",
                            },
                        },
                        {
                            "key": "unittest-controller2",
                            "doc_count": 1,
                            "runs": {
                                "value": 1.6,
                                "value_as_string": "2020-09-26T20:19:15.810Z",
                            },
                        },
                    ],
                }
            },
        }

        index = self.build_index(server_config, ("2020-08", "2020-09", "2020-10"))
        response = query_helper(json, index, 200, server_config, json=response_payload)
        res_json = response.json
        assert isinstance(res_json, list)
        assert len(res_json) == 2
        assert res_json[0]["key"] == "unittest-controller1"
        assert res_json[0]["controller"] == "unittest-controller1"
        assert res_json[0]["results"] == 2
        assert res_json[0]["last_modified_value"] == 1.59847315581e12
        assert res_json[0]["last_modified_string"] == "2020-08-26T20:19:15.810Z"
        assert res_json[1]["key"] == "unittest-controller2"
        assert res_json[1]["controller"] == "unittest-controller2"
        assert res_json[1]["results"] == 1
        assert res_json[1]["last_modified_value"] == 1.6
        assert res_json[1]["last_modified_string"] == "2020-09-26T20:19:15.810Z"

    @pytest.mark.parametrize(
        "exceptions",
        (
            {"exception": requests.exceptions.HTTPError, "status": 500},
            {"exception": requests.exceptions.ConnectionError, "status": 502},
            {"exception": requests.exceptions.Timeout, "status": 504},
            {"exception": requests.exceptions.InvalidURL, "status": 500},
            {"exception": Exception, "status": 500},
        ),
    )
    def test_http_error(self, client, server_config, query_helper, exceptions):
        """
        test_http_error Check that an Elasticsearch error is reported
        correctly.
       """
        json = {
            "user": "drb",
            "start": "2020-08",
            "end": "2020-08",
        }
        index = self.build_index(server_config, ("2020-08",))
        query_helper(
            json,
            index,
            exceptions["status"],
            server_config,
            exc=exceptions["exception"],
        )
