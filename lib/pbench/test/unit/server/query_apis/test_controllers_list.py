import pytest
import requests
from http import HTTPStatus


class TestControllersList:
    """
    Unit testing for resources/ControllersList class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

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
        response = client.post(
            f"{server_config.rest_uri}/controllers/list",
            headers={"Authorization": "Bearer " + pbench_token},
            json={"user": "pp", "start": "2020-08", "end": "2020-10"},
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    @pytest.mark.parametrize(
        "user", ("drb", "pp"),
    )
    def test_accessing_user_data_with_invalid_token(
        self, client, server_config, pbench_token, user
    ):
        """
        Test behavior when Authorization header does not have access to other user's data
        """
        # valid token logout
        response = client.post(
            f"{server_config.rest_uri}/logout",
            headers=dict(Authorization="Bearer " + pbench_token),
        )
        assert response.status_code == HTTPStatus.OK
        response = client.post(
            f"{server_config.rest_uri}/controllers/list",
            headers={"Authorization": "Bearer " + pbench_token},
            json={"user": user, "start": "2020-08", "end": "2020-10"},
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_missing_json_object(self, client, server_config, pbench_token):
        """
        Test behavior when no JSON payload is given
        """
        response = client.post(
            f"{server_config.rest_uri}/controllers/list",
            headers={"Authorization": "Bearer " + pbench_token},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == "Invalid request payload"

    @pytest.mark.parametrize(
        "keys",
        (
            {"user": "x"},
            {"start": "2020"},
            {"end": "2020"},
            {"user": "x", "start": "2020"},
            {"user": "x", "end": "2020"},
            {"some_additional_key": "test"},
        ),
    )
    def test_missing_keys(self, client, server_config, keys, user_ok, pbench_token):
        """
        Test behavior when JSON payload does not contain all required keys.

        Note that "start", and "end" are required whereas "user" is not mandatory;
        however, Pbench will silently ignore any additional keys that are
        specified.
       """
        response = client.post(
            f"{server_config.rest_uri}/controllers/list",
            headers={"Authorization": "Bearer " + pbench_token},
            json=keys,
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        missing = [k for k in ("start", "end") if k not in keys]
        assert (
            response.json.get("message")
            == f"Missing required parameters: {','.join(missing)}"
        )

    def test_bad_dates(self, client, server_config, user_ok, pbench_token):
        """
        Test behavior when a bad date string is given
        """
        response = client.post(
            f"{server_config.rest_uri}/controllers/list",
            headers={"Authorization": "Bearer " + pbench_token},
            json={"user": "drb", "start": "2020-12", "end": "2020-19"},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert (
            response.json.get("message")
            == "Value '2020-19' (str) cannot be parsed as a date/time string"
        )

    @pytest.mark.parametrize(
        "user", ("drb", "", "no_user", None),
    )
    def test_query(
        self,
        client,
        server_config,
        query_api,
        user_ok,
        find_template,
        build_auth_header,
        user,
    ):
        """
        Check the construction of Elasticsearch query URI and filtering of the response body.
        The test will run once with each parameter supplied from the local parameterization,
        and, for each of those, three times with different values of the build_auth_header fixture.
        """
        json = {
            "user": user,
            "start": "2020-08",
            "end": "2020-10",
        }
        if user == "no_user":
            json.pop("user", None)

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
        # If we're not asking about a particular user, or if the user
        # field is to be omitted altogether, or if we have a valid
        # token, then the request should succeed.
        if (
            not user
            or user == "no_user"
            or build_auth_header["header_param"] == "valid"
        ):
            expected_status = HTTPStatus.OK
        else:
            expected_status = HTTPStatus.FORBIDDEN

        response = query_api(
            "/controllers/list",
            "/_search?ignore_unavailable=true",
            json,
            index,
            expected_status,
            headers=build_auth_header["header"],
            status=expected_status,
            json=response_payload,
        )
        assert response.status_code == expected_status
        if response.status_code == HTTPStatus.OK:
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
                "total": {"value": 0, "relation": "eq"},
                "max_score": None,
                "hits": [],
            },
        }

        expected_status = HTTPStatus.OK
        if build_auth_header["header_param"] != "valid":
            expected_status = HTTPStatus.FORBIDDEN

        index = self.build_index(server_config, ("2020-08", "2020-09", "2020-10"))
        response = query_api(
            "/controllers/list",
            "/_search?ignore_unavailable=true",
            json,
            index,
            expected_status,
            headers=build_auth_header["header"],
            status=HTTPStatus.OK,
            json=response_payload,
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
        self, server_config, query_api, exceptions, user_ok, find_template
    ):
        """
        Check that an exception in calling Elasticsearch is reported correctly.
        """
        json = {
            "user": "",
            "start": "2020-08",
            "end": "2020-08",
        }
        index = self.build_index(server_config, ("2020-08",))
        query_api(
            "/controllers/list",
            "/_search?ignore_unavailable=true",
            json,
            index,
            exceptions["status"],
            body=exceptions["exception"],
        )

    @pytest.mark.parametrize("errors", (400, 500, 409))
    def test_http_error(self, server_config, query_api, errors, user_ok, find_template):
        """
        Check that an Elasticsearch error is reported correctly through the
        response.raise_for_status() and Pbench handlers.
        """
        json = {
            "user": "",
            "start": "2020-08",
            "end": "2020-08",
        }
        index = self.build_index(server_config, ("2020-08",))
        query_api(
            "/controllers/list",
            "/_search?ignore_unavailable=true",
            json,
            index,
            HTTPStatus.BAD_GATEWAY,
            status=errors,
        )
