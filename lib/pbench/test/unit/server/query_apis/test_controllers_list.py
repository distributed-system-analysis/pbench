import pytest
from http import HTTPStatus
from pbench.server.api.resources.query_apis.controllers_list import ControllersList
from pbench.test.unit.server.query_apis.commons import Commons


class TestControllersList(Commons):
    """
    Unit testing for resources/ControllersList class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    @pytest.fixture(autouse=True)
    def _setup(self):
        super()._setup(
            pbench_endpoint="/controllers/list",
            elastic_endpoint="/_search?ignore_unavailable=true",
            payload={"user": "drb", "start": "2020-08", "end": "2020-10"},
            bad_date_payload={"user": "drb", "start": "2020-12", "end": "2020-19"},
            error_payload={"start": "2020-08", "end": "2020-08"},
            empty_response_payload={
                "took": 1,
                "timed_out": False,
                "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
                "hits": {
                    "total": {"value": 0, "relation": "eq"},
                    "max_score": None,
                    "hits": [],
                },
            },
        )

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
    def test_missing_keys(
        self, client, server_config, keys, find_template, user_ok, pbench_token
    ):
        """
        Test behavior when JSON payload does not contain all required keys.

        Note that "start", and "end" are required whereas "user" is not mandatory;
        however, Pbench will silently ignore any additional keys that are
        specified.
       """
        self.required_keys = [
            key
            for key, parameter in ControllersList(
                client.config, client.logger
            ).schema.parameters.items()
            if parameter.required
        ]
        self.missing_keys(client, server_config, keys, user_ok, pbench_token)

    @pytest.mark.parametrize(
        "user", ("drb", "badwolf", "no_user"),
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
        pbench_token,
    ):
        """
        Check the construction of Elasticsearch query URI and filtering of the response body.
        The test will run once with each parameter supplied from the local parameterization,
        and, for each of those, three times with different values of the build_auth_header fixture.
        """
        payload = {
            "user": user,
            "access": "private",
            "start": "2020-08",
            "end": "2020-10",
        }
        # "no_user" means omitting the "user" parameter entirely.
        if user == "no_user":
            payload.pop("user", None)
        if user == "no_user" or user is None:
            payload["access"] = "public"

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

        # Determine whether we should expect the request to succeed, or to
        # fail with a permission error. We always authenticate with the
        # user "drb" as fabricated by the build_auth_header fixure; we
        # don't expect success for an "invalid" authentication, for a different
        # user, or for an invalid username.
        if (
            not user
            or user == "no_user"
            or build_auth_header["header_param"] == "valid"
        ) and user != "badwolf":
            expected_status = HTTPStatus.OK
        else:
            expected_status = HTTPStatus.FORBIDDEN

        response = query_api(
            "/controllers/list",
            "/_search?ignore_unavailable=true",
            payload,
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
