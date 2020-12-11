import pytest
import re
import requests

from pbench.server.api.resources.query_apis import get_es_url


@pytest.fixture
def get_helper(client, server_config, requests_mock):
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

    def get_helper(expected_status, server_config, **kwargs):
        es_url = get_es_url(server_config)
        requests_mock.get(re.compile(f"{es_url}"), **kwargs)
        response = client.get(f"{server_config.rest_uri}/controllers/months")
        assert requests_mock.last_request.url == (es_url + "/_aliases")
        assert response.status_code == expected_status
        return response

    return get_helper


class TestQueryMonthIndices:
    """
    Unit testing for resources/QueryMonthIndices class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    def test_query(self, client, server_config, get_helper):
        """
        test_query Check the construction of Elasticsearch query URI
        and filtering of the response body.
        """
        response_payload = {
            ".opendistro-alerting-alert-history-2020.12.05-000177": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.11-000153": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.12-000154": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.22-000164": {"aliases": {}},
            "unit-test.v5.result-data-sample.2020-04-29": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.12.02-000174": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.12.03-000175": {"aliases": {}},
            "unit-test.v6.run-toc.2020-11": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.13-000155": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.18-000160": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.30-000172": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.29-000171": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.28-000170": {"aliases": {}},
            "unit-test.v6.run-toc.2020-12": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.21-000163": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.12.06-000178": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.12.01-000173": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.24-000166": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.26-000168": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.14-000156": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.15-000157": {"aliases": {}},
            "unit-test.v5.result-data.2020-04-29": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.19-000161": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.12.10-000182": {
                "aliases": {".opendistro-alerting-alert-history-write": {}}
            },
            ".opendistro-alerting-alert-history-2020.11.27-000169": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.12.08-000180": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.17-000159": {"aliases": {}},
            "unit-test.v6.run-data.2020-12": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.12.04-000176": {"aliases": {}},
            "unit-test.v6.run-data.2020-04": {"aliases": {}},
            ".kibana_2": {"aliases": {".kibana": {}}},
            ".opendistro-alerting-alert-history-2020.11.23-000165": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.12.07-000179": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.12.09-000181": {"aliases": {}},
            ".opendistro-alerting-alerts": {"aliases": {}},
            ".kibana_1": {"aliases": {}},
            "unit-test.v6.run-toc.2020-04": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.25-000167": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.16-000158": {"aliases": {}},
            ".opendistro-alerting-alert-history-2020.11.20-000162": {"aliases": {}},
            "unit-test.v4.server-reports.2020-12": {"aliases": {}},
            "unit-test.v6.run-data.2020-11": {"aliases": {}},
        }

        response = get_helper(200, server_config, json=response_payload)
        res_json = response.json
        assert isinstance(res_json, list)
        assert len(res_json) == 3
        assert res_json[0] == "2020-12"
        assert res_json[1] == "2020-11"
        assert res_json[2] == "2020-04"

    @pytest.mark.parametrize(
        "exceptions",
        (
            {"exception": requests.exceptions.HTTPError, "status": 502},
            {"exception": requests.exceptions.ConnectionError, "status": 502},
            {"exception": requests.exceptions.Timeout, "status": 504},
            {"exception": requests.exceptions.InvalidURL, "status": 500},
            {"exception": Exception, "status": 500},
        ),
    )
    def test_http_error(self, client, server_config, get_helper, exceptions):
        """
        test_http_error Check that an Elasticsearch error is reported
        correctly.
        """
        get_helper(
            exceptions["status"], server_config, exc=exceptions["exception"],
        )
