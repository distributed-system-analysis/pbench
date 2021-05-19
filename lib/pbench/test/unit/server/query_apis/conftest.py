import pytest
import requests
from requests.exceptions import HTTPError


def make_http_exception(status: int) -> HTTPError:
    """
    Helper to create a properly annotated HTTPError for testing

    Args:
        status: HTTP status code

    Returns:
        HTTPError object
    """
    response = requests.Response()
    response.status_code = status
    response.reason = "Fake reason"
    return HTTPError(response=response)


@pytest.fixture
def query_api(client, server_config, requests_mock, request):
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

    NOTE: the expected URI for the server query and the resulting Elasticsearch
    query come from a test case parameter, which is passed through the Pytest
    "mark" mechanism and accessed through the "param" attribute of the Pytest
    request fixture. E.g.,

            @pytest.mark.parametrize(
                "query_api",
                [
                    {
                        "pbench": "/controllers/list",
                        "elastic": "/_search?ignore_unavailable=true",
                    }
                ],
                indirect=True,
            )

    The first parameter must match the name of this fixture, and the second should
    be a list (or tuple) with a single dict defining the "pbench" and "elastic"
    URI paths.

    :return: the response object for further checking
    """

    def query_api(payload, expected_index, expected_status, server_config, **kwargs):
        host = server_config.get("elasticsearch", "host")
        port = server_config.get("elasticsearch", "port")
        es_url = f"http://{host}:{port}{expected_index}{request.param['elastic']}"
        requests_mock.post(es_url, **kwargs)
        response = client.post(
            f"{server_config.rest_uri}{request.param['pbench']}", json=payload
        )
        assert requests_mock.last_request.url == es_url
        assert response.status_code == expected_status
        return response

    return query_api
