from http import HTTPStatus

import pytest

from pbench.server.api.resources import ApiMethod
from pbench.server.api.resources.query_apis.datasets.datasets import Datasets
from pbench.server.database.models.datasets import Dataset, DatasetNotFound, Metadata
from pbench.test.unit.server.query_apis.commons import Commons

EMPTY_DELDATE_RESPONSE = {
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


class TestDatasets(Commons):
    """
    Unit testing for resources/DatasetsDetail class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

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
        "user,ao,expected_status",
        [
            ("drb", False, HTTPStatus.OK),
            ("drb", True, HTTPStatus.OK),
            ("test_admin", False, HTTPStatus.OK),
            ("test", False, HTTPStatus.FORBIDDEN),
            (None, False, HTTPStatus.UNAUTHORIZED),
        ],
    )
    def test_empty_delete(
        self,
        client,
        server_config,
        query_api,
        find_template,
        user,
        ao,
        expected_status,
        get_token_func,
    ):
        """Check deletion with no Elasticsearch documents"""

        headers = None

        if user:
            token = get_token_func(user)
            assert token
            headers = {"authorization": f"bearer {token}"}

        if ao:
            # Set archiveonly flag to disable index-map logic
            drb = Dataset.query(name="drb")
            Metadata.setvalue(drb, Metadata.SERVER_ARCHIVE, True)
            index = None
        else:
            index = self.build_index_from_metadata()

        response = query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            payload=None,
            expected_index=index,
            expected_status=expected_status,
            request_method=self.api_method,
            json=EMPTY_DELDATE_RESPONSE,
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

            # On success, the dataset should be gone
            with pytest.raises(DatasetNotFound):
                Dataset.query(name="drb")
        else:
            # On failure, the dataset should still exist
            assert Dataset.query(name="drb")
            assert response.json["message"].endswith(
                "is not authorized to DELETE a resource owned by drb with private access"
            )

    @pytest.mark.parametrize(
        "user,ao,expected_status",
        [
            ("drb", False, HTTPStatus.OK),
            ("drb", True, HTTPStatus.OK),
            ("test_admin", False, HTTPStatus.OK),
            ("test", False, HTTPStatus.FORBIDDEN),
            (None, False, HTTPStatus.UNAUTHORIZED),
        ],
    )
    def test_empty_update_access(
        self,
        client,
        server_config,
        query_api,
        find_template,
        user,
        ao,
        expected_status,
        get_token_func,
    ):
        """Check update with no Elasticsearch documents"""

        headers = None

        if user:
            token = get_token_func(user)
            assert token
            headers = {"authorization": f"bearer {token}"}

        if ao:
            # Set archiveonly flag to disable index-map logic
            drb = Dataset.query(name="drb")
            Metadata.setvalue(drb, Metadata.SERVER_ARCHIVE, True)
            index = None
        else:
            index = self.build_index_from_metadata()

        response = query_api(
            "/datasets/random_md5_string1?access=public",
            "/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=expected_status,
            request_method=ApiMethod.POST,
            json=EMPTY_DELDATE_RESPONSE,
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

            # On success, the dataset should be updated
            drb = Dataset.query(name="drb")
            assert "public" == drb.access
        else:
            # On failure, the dataset should still exist
            assert Dataset.query(name="drb")
            assert response.json["message"].endswith(
                "is not authorized to UPDATE a resource owned by drb with private access"
            )

    @pytest.mark.parametrize("ao", (True, False))
    def test_empty_get(
        self, client, server_config, query_api, find_template, build_auth_header, ao
    ):
        """Check a GET operation with no Elasticsearch documents"""
        auth_json = {"user": "drb", "access": "private"}

        expected_status = self.get_expected_status(
            auth_json, build_auth_header["header_param"]
        )

        if ao:
            # Set archiveonly flag to disable index-map logic
            drb = Dataset.query(name="drb")
            Metadata.setvalue(drb, Metadata.SERVER_ARCHIVE, True)
            index = None
            if expected_status == HTTPStatus.OK:
                expected_status = HTTPStatus.CONFLICT
        else:
            index = self.build_index_from_metadata()

        response = query_api(
            f"{self.pbench_endpoint}",
            "/_search?ignore_unavailable=true",
            self.payload,
            index,
            expected_status,
            request_method=ApiMethod.GET,
            headers=build_auth_header["header"],
            json=self.empty_es_response_payload,
        )
        assert response.status_code == expected_status
        if expected_status == HTTPStatus.OK:
            assert [] == response.json
        elif expected_status == HTTPStatus.CONFLICT:
            assert {"message": "Dataset indexing was disabled"} == response.json
        else:
            assert {
                "message": "Unauthenticated client is not authorized to READ a resource owned by drb with private access"
            } == response.json
