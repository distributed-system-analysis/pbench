import pytest
import requests

from http import HTTPStatus
from typing import AnyStr, Type

from pbench.server.api.resources.query_apis import ElasticBase, JSON, ParamType


class Commons:
    """
    Unit testing for all the elasticsearch resources class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    # Declare the common empty search response payload that subclass can use.
    empty_es_response_payload = {
        "took": 1,
        "timed_out": False,
        "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
        "hits": {
            "total": {"value": 0, "relation": "eq"},
            "max_score": None,
            "hits": [],
        },
    }

    def _setup(
        self,
        cls_obj: Type[ElasticBase] = None,
        pbench_endpoint: AnyStr = None,
        elastic_endpoint: AnyStr = None,
        payload: JSON = None,
        bad_date_payload: JSON = None,
        error_payload: JSON = None,
        empty_es_response_payload: JSON = None,
    ):
        self.cls_obj = cls_obj
        self.pbench_endpoint = pbench_endpoint
        self.elastic_endpoint = elastic_endpoint
        self.payload = payload
        self.bad_date_payload = bad_date_payload
        self.error_payload = error_payload
        self.empty_es_response_payload = empty_es_response_payload

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
        if "user" not in self.cls_obj.schema.parameters.keys():
            pytest.skip("skipping non accessible user data test")
        self.payload["user"] = "pp"
        response = client.post(
            server_config.rest_uri + self.pbench_endpoint,
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
        if "user" not in self.cls_obj.schema.parameters.keys():
            pytest.skip("skipping accessing user data with invalid token test")
        # valid token logout
        response = client.post(
            server_config.rest_uri + "/logout",
            headers={"Authorization": "Bearer " + pbench_token},
        )
        assert response.status_code == HTTPStatus.OK
        self.payload["user"] = user
        response = client.post(
            server_config.rest_uri + self.pbench_endpoint,
            headers={"Authorization": "Bearer " + pbench_token},
            json=self.payload,
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_missing_json_object(self, client, server_config, pbench_token):
        """
        Test behavior when no JSON payload is given
        """
        response = client.post(
            server_config.rest_uri + self.pbench_endpoint,
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
        required_keys = [
            key
            for key, parameter in self.cls_obj.schema.parameters.items()
            if parameter.required
        ]
        response = client.post(
            server_config.rest_uri + self.pbench_endpoint,
            headers={"Authorization": "Bearer " + pbench_token},
            json=keys,
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        missing = [k for k in required_keys if k not in keys]
        assert (
            response.json.get("message")
            == f"Missing required parameters: {','.join(missing)}"
        )

    def test_bad_dates(self, client, server_config, user_ok, pbench_token):
        """
        Test behavior when a bad date string is given
        """
        parameter_types = [
            parameter.type
            for _, parameter in self.cls_obj.schema.parameters.items()
            if parameter.required
        ]
        if ParamType.DATE not in parameter_types or not all(
            k in self.payload for k in ("start", "end")
        ):
            pytest.skip("skipping the bad date test")

        # Modify start and end time in the payload to make it look invalid
        self.payload["start"] = "2020-12"
        self.payload["end"] = "2020-19"
        response = client.post(
            server_config.rest_uri + self.pbench_endpoint,
            headers={"Authorization": "Bearer " + pbench_token},
            json=self.payload,
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
        PyTest will run this test multiple times with different values of the build_auth_header
        fixture.
        """
        if not self.empty_es_response_payload or not self.elastic_endpoint:
            pytest.skip("skipping the empty query test")
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
            json=self.empty_es_response_payload,
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
        if not self.elastic_endpoint:
            pytest.skip("skipping the http exception test")

        # Make the start and end time in payload the same to result in an exception
        self.payload["end"] = self.payload["start"]

        index = self.build_index(server_config, ("2020-08",))
        query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.payload,
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
        if not self.elastic_endpoint:
            pytest.skip("skipping the http error test")

        # Make the start and end time in payload the same to result in an error
        self.payload["end"] = self.payload["start"]

        index = self.build_index(server_config, ("2020-08",))
        query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.payload,
            index,
            HTTPStatus.BAD_GATEWAY,
            status=errors,
            headers={"Authorization": "Bearer " + pbench_token},
        )
