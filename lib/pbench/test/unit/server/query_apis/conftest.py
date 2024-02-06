from http import HTTPStatus
from typing import Any, Dict, Optional

import pytest
import requests
import responses

from pbench.server import JSONOBJECT
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
    """

    def query_api(
        pbench_uri: str,
        es_uri: str,
        payload: Dict[str, Any],
        expected_index: str,
        expected_status: str,
        headers: Optional[dict] = None,
        request_method=ApiMethod.POST,
        query_params: Optional[JSONOBJECT] = None,
        **kwargs,
    ) -> requests.Response:
        """Execute an Elasticsearch query with conditional mocking

        BEWARE: the logic around installing the Elasticsearch mock is tricky.
        The responses package will cause a test case to failure if an installed
        mock isn't called, so we need to be careful in analyzing the parameters
        to determine whether a call is expected. This is mostly based on the
        expected status and index values plus a few special cases!

        Args:
            pbench_uri: The Pbench API path to call
            es_uri: The Elasticsearch URI to mock
            payload: The Pbench API JSON payload
            expected_index: The expected Elasticsearch index string
            expected_status: The expected API status
            headers: Pbench API call headers (usually authentication)
            request_method: The Pbench API call method
            query_params: The Pbench API query parameters

        Returns:
            The Pbench API response object
        """
        base_uri = server_config.get("Indexing", "uri")
        es_url = f"{base_uri}{expected_index}{es_uri}"
        client_method = getattr(client, request_method.name.lower())
        if request_method == ApiMethod.GET:
            es_method = responses.GET
            assert not payload
        else:
            es_method = responses.POST
        with responses.RequestsMock() as rsp:
            # We need to set up mocks for the Server's call to Elasticsearch,
            # which will only be made if we don't expect Pbench to fail before
            # making the call. We never expect an Elasticsearch call when the
            # expected status is FORBIDDEN or UNAUTHORIZED; or when we give the
            # canonical "bad username" (badwolf) and are expecting NOT_FOUND.
            if (
                expected_status
                not in [
                    HTTPStatus.FORBIDDEN,
                    HTTPStatus.UNAUTHORIZED,
                    HTTPStatus.BAD_REQUEST,
                ]
                and (
                    expected_status != HTTPStatus.NOT_FOUND
                    or request_method != ApiMethod.POST
                    or payload.get("user") != "badwolf"
                )
                and expected_index is not None
            ):
                rsp.add(es_method, es_url, **kwargs)
            response = client_method(
                f"{server_config.rest_uri}{pbench_uri}",
                headers=headers if headers else {},
                json=payload,
                query_string=query_params,
            )
            assert (
                response.status_code == expected_status
            ), f"Unexpected status {response.status_code}: {response.text!r}"
            return response

    return query_api
