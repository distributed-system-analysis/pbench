from http import HTTPStatus
from typing import Any, Dict

import pytest
import requests
import responses

from pbench.server import JSON
from pbench.server.api.resources import ApiMethod


@pytest.fixture
@responses.activate
def query_api(client, server_config, provide_metadata):
    """
    Help controller queries that want to interact with a mocked
    Elasticsearch service.

    This is a fixture which exposes a function of the same name that can be
    used to set up and validate a mocked Elasticsearch query with a JSON
    payload and an expected status.

    Parameters to the mocked Elasticsearch POST are passed as keyword
    parameters: these can be any of the parameters supported by the
    responses mock. Exceptions are specified by providing an Exception()
    instance as the 'body'.

    :return: the response object for further checking
    """

    def query_api(
        pbench_uri: str,
        es_uri: str,
        payload: Dict[str, Any],
        expected_index: str,
        expected_status: str,
        headers: dict = {},
        request_method=ApiMethod.POST,
        query_params: JSON = None,
        **kwargs,
    ) -> requests.Response:
        host = server_config.get("elasticsearch", "host")
        port = server_config.get("elasticsearch", "port")
        es_url = f"http://{host}:{port}{expected_index}{es_uri}"
        assert request_method in (ApiMethod.GET, ApiMethod.POST)
        if request_method == ApiMethod.GET:
            es_method = responses.GET
            client_method = client.get
            assert not payload
        else:
            es_method = responses.POST
            client_method = client.post
        with responses.RequestsMock() as rsp:
            # We need to set up mocks for the Server's call to Elasticsearch,
            # which will only be made if we don't expect Pbench to fail before
            # making the call. We never expect an Elasticsearch call when the
            # expected status is FORBIDDEN or UNAUTHORIZED; or when we give the
            # canonical "bad username" (badwolf) and are expecting NOT_FOUND.
            if expected_status not in [
                HTTPStatus.FORBIDDEN,
                HTTPStatus.UNAUTHORIZED,
            ] and (
                expected_status != HTTPStatus.NOT_FOUND
                or request_method != ApiMethod.POST
                or payload.get("user") != "badwolf"
            ):
                rsp.add(es_method, es_url, **kwargs)
            response = client_method(
                f"{server_config.rest_uri}{pbench_uri}",
                headers=headers,
                json=payload,
                query_string=query_params,
            )
        assert response.status_code == expected_status
        return response

    return query_api
