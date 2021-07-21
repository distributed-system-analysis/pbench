import pytest
import requests
from http import HTTPStatus
from typing import Any, AnyStr, Dict


class Commons:
    """
    Unit testing for all the elasticsearch resources class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    def _setup(
        self,
        pbench_endpoint: AnyStr = None,
        elastic_endpoint: AnyStr = None,
        payload: [AnyStr, Any] = None,
        bad_date_payload: [AnyStr, Any] = None,
        error_payload: Dict[AnyStr, Any] = None,
        empty_response_payload: Dict[AnyStr, Any] = None,
    ):
        self.pbench_endpoint = pbench_endpoint
        self.elastic_endpoint = elastic_endpoint
        self.payload = payload
        self.bad_date_payload = bad_date_payload
        self.error_payload = error_payload
        self.empty_response_payload = empty_response_payload

    def build_index(self, server_config, dates):
        """
        Build the index list for query

        Args:
            dates (iterable): list of date strings
        """
        idx = server_config.get("Indexing", "index_prefix") + ".v6.run-data."
        index = "/"
        for d in dates:
            index += f"{idx}{d},"
        return index

    def test_non_accessible_user_data(self, client, server_config, pbench_token):
        """
        Test behavior when Authorization header does not have access to other user's data
        """
        # The pbench_token fixture logs in as user "drb"
        # Trying to access the data belong to the user "pp"
        if not self.payload.get("user", None):
            pytest.skip("skipping non accessible user data test")
        self.payload["user"] = "pp"
        response = client.post(
            f"{server_config.rest_uri}{self.pbench_endpoint}",
            headers={"Authorization": "Bearer " + pbench_token},
            json=self.payload,
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    @pytest.mark.parametrize(
        "user", ("drb", "pp"),
    )
    def test_accessing_user_data_with_invalid_token(
        self, client, server_config, pbench_token, user
    ):
        """
        Test behavior when expired Authorization header provided
        """
        if not self.payload.get("user", None):
            pytest.skip("skipping accessing user data with invalid token test")
        # valid token logout
        response = client.post(
            f"{server_config.rest_uri}/logout",
            headers=dict(Authorization="Bearer " + pbench_token),
        )
        assert response.status_code == HTTPStatus.OK
        self.payload["user"] = user
        response = client.post(
            f"{server_config.rest_uri}{self.pbench_endpoint}",
            headers={"Authorization": "Bearer " + pbench_token},
            json=self.payload,
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_missing_json_object(self, client, server_config, pbench_token):
        """
        Test behavior when no JSON payload is given
        """
        response = client.post(
            f"{server_config.rest_uri}{self.pbench_endpoint}",
            headers={"Authorization": "Bearer " + pbench_token},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == "Invalid request payload"

    def missing_keys(self, client, server_config, keys, user_ok, pbench_token):
        """
        Test behavior when JSON payload does not contain all required keys.

        Note that Pbench will silently ignore any additional keys that are
        specified but not required.
       """
        response = client.post(
            f"{server_config.rest_uri}{self.pbench_endpoint}",
            headers={"Authorization": "Bearer " + pbench_token},
            json=keys,
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        missing = [k for k in self.required_keys if k not in keys]
        assert (
            response.json.get("message")
            == f"Missing required parameters: {','.join(missing)}"
        )

    def test_bad_dates(self, client, server_config, user_ok, pbench_token):
        """
        Test behavior when a bad date string is given
        """
        if not self.bad_date_payload:
            pytest.skip("skipping the bad date test")
        response = client.post(
            f"{server_config.rest_uri}{self.pbench_endpoint}",
            headers={"Authorization": "Bearer " + pbench_token},
            json=self.bad_date_payload,
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert (
            response.json.get("message")
            == "Value '2020-19' (str) cannot be parsed as a date/time string"
        )

    def test_empty_query(
        self,
        client,
        server_config,
        query_api,
        user_ok,
        find_template,
        build_auth_header,
    ):
        """
        Check proper handling of a query resulting in no Elasticsearch matches.
        The test will run thrice with different values of the build_auth_header
        fixture.
        """
        if not self.empty_response_payload or not self.elastic_endpoint:
            pytest.skip(
                "skipping the empty query test since the empty response payload is not set"
            )
        expected_status = HTTPStatus.OK
        if build_auth_header["header_param"] != "valid":
            expected_status = HTTPStatus.FORBIDDEN

        index = self.build_index(server_config, ("2020-08", "2020-09", "2020-10"))
        response = query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.payload,
            index,
            expected_status,
            headers=build_auth_header["header"],
            status=HTTPStatus.OK,
            json=self.empty_response_payload,
        )
        assert response.status_code == expected_status
        if response.status_code == HTTPStatus.OK:
            assert response.json == []

    @pytest.mark.parametrize(
        "exceptions",
        (
            {
                "exception": requests.exceptions.ConnectionError(),
                "status": HTTPStatus.BAD_GATEWAY,
            },
            {
                "exception": requests.exceptions.Timeout(),
                "status": HTTPStatus.GATEWAY_TIMEOUT,
            },
            {
                "exception": requests.exceptions.InvalidURL(),
                "status": HTTPStatus.INTERNAL_SERVER_ERROR,
            },
            {"exception": Exception(), "status": HTTPStatus.INTERNAL_SERVER_ERROR},
            {"exception": ValueError(), "status": HTTPStatus.INTERNAL_SERVER_ERROR},
        ),
    )
    def test_http_exception(
        self,
        server_config,
        query_api,
        exceptions,
        user_ok,
        find_template,
        pbench_token,
    ):
        """
        Check that an exception in calling Elasticsearch is reported correctly.
        """
        if not self.elastic_endpoint or not self.error_payload:
            pytest.skip("skipping the http exception test")
        index = self.build_index(server_config, ("2020-08",))
        query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.error_payload,
            index,
            exceptions["status"],
            body=exceptions["exception"],
            headers={"Authorization": "Bearer " + pbench_token},
        )

    @pytest.mark.parametrize("errors", (400, 500, 409))
    def test_http_error(
        self, server_config, query_api, user_ok, find_template, pbench_token, errors
    ):
        """
        Check that an Elasticsearch error is reported correctly through the
        response.raise_for_status() and Pbench handlers.
        """
        if not self.elastic_endpoint or not self.error_payload:
            pytest.skip("skipping the http error test")
        index = self.build_index(server_config, ("2020-08",))
        query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.error_payload,
            index,
            HTTPStatus.BAD_GATEWAY,
            status=errors,
            headers={"Authorization": "Bearer " + pbench_token},
        )
