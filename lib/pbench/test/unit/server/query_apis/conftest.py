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
        expect_call: Optional[bool] = None,
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
            expect_call: True to force ES mock, False to suppress
            kwargs: Additional mock parameters
                body: Used to cause an exception to be raised
                status: Set the mock response status

        Returns:
            The Pbench API response object
        """
        base_uri = server_config.get("Indexing", "uri")
        idx = expected_index if expected_index is not None else "/"
        es_url = f"{base_uri}{idx}{es_uri}"
        client_method = getattr(client, request_method.name.lower())
        if request_method == ApiMethod.GET:
            es_method = responses.GET
            assert not payload
        else:
            es_method = responses.POST
        with responses.RequestsMock() as rsp:
            # We need to set up mocks for the Server's call to Elasticsearch,
            # which will only be made if we don't expect Pbench to fail before
            # making the call. The responses package will fail a test if the
            # mock is installed but not called, so we have to get this right.
            #
            # Generally if the expected API status is OK, we assume we'll call
            # Elasticsearch; similarly, if we're setting a return "body" or
            # "status" on the mock, we assume we intend to make the call.
            #
            # In less straightforward cases, the expect_call parameter can be
            # used to force or prevent the mock (with the default None value
            # being neutral).
            if (
                expected_status == HTTPStatus.OK
                or isinstance(kwargs.get("body"), Exception)
                or isinstance(kwargs.get("status"), int)
                or expect_call is True
            ) and expect_call is not False:
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
