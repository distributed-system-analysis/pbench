from http import HTTPStatus

import pytest

from pbench.server.api.resources import ApiMethod
from pbench.server.api.resources.query_apis.datasets.datasets import Datasets
from pbench.test.unit.server.query_apis.commons import Commons


class TestDatasetsDelete(Commons):
    """
    Unit testing for resources/DatasetsDetail class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    EMPTY_DELETE_RESPONSE = {
        "took": 42,
        "timed_out": False,
        "total": 0,
        "deleted": 0,
        "batches": 0,
        "version_conflicts": 0,
        "noops": 0,
        "retries": {"bulk": 0, "search": 0},
        "throttled_millis": 0,
        "requests_per_second": 0.0,
        "throttled_until_millis": 0,
        "failures": [],
    }

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        super()._setup(
            cls_obj=Datasets(client.config),
            pbench_endpoint="/datasets/random_md5_string1",
            elastic_endpoint="/_delete_by_query?ignore_unavailable=true&refresh=true",
            index_from_metadata=None,
            empty_es_response_payload=self.EMPTY_ES_RESPONSE_PAYLOAD,
            api_method=ApiMethod.DELETE,
            use_index_map=True,
        )

    @pytest.mark.parametrize(
        "user, expected_status",
        [
            ("drb", HTTPStatus.OK),
            ("test_admin", HTTPStatus.OK),
            ("test", HTTPStatus.FORBIDDEN),
            (None, HTTPStatus.UNAUTHORIZED),
        ],
    )
    def test_query(
        self,
        client,
        server_config,
        query_api,
        find_template,
        user,
        expected_status,
        get_token_func,
    ):
        """
        Check the construction of Elasticsearch query URI and filtering of the response body.
        The test will run once with each parameter supplied from the local parameterization.
        """

        headers = None

        if user:
            token = get_token_func(user)
            assert token
            headers = {"authorization": f"bearer {token}"}

        response_payload = self.EMPTY_DELETE_RESPONSE

        index = self.build_index_from_metadata()

        response = query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            payload=None,
            expected_index=index,
            expected_status=expected_status,
            request_method=self.api_method,
            json=response_payload,
            headers=headers,
        )
        assert response.status_code == expected_status
        if response.status_code == HTTPStatus.OK:
            res_json = response.json
            expected = {
                "total": 0,
                "updated": 0,
                "deleted": 0,
                "failures": 0,
                "version_conflicts": 0,
            }
            assert expected == res_json

    def test_empty_query(
        self,
        client,
        server_config,
        query_api,
        find_template,
        build_auth_header,
    ):
        """
        Check the handling of a query that doesn't return any data.
        The test will run thrice with different values of the build_auth_header
        fixture.
        """
        auth_json = {"user": "drb", "access": "private"}

        expected_status = self.get_expected_status(
            auth_json, build_auth_header["header_param"]
        )

        index = self.build_index_from_metadata()

        response = query_api(
            f"{self.pbench_endpoint}",
            self.elastic_endpoint,
            self.payload,
            index,
            expected_status,
            request_method=self.api_method,
            headers=build_auth_header["header"],
            json=self.empty_es_response_payload,
        )
        assert response.status_code == expected_status
