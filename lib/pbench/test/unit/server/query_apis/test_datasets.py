import copy
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
        "user,ao,owner,access,expected_status",
        [
            ("drb", False, None, "public", HTTPStatus.OK),
            ("drb", True, None, "public", HTTPStatus.OK),
            ("test_admin", False, "test", None, HTTPStatus.OK),
            ("test", False, None, "public", HTTPStatus.FORBIDDEN),
            (None, False, None, "public", HTTPStatus.UNAUTHORIZED),
            ("drb", False, "test", "public", HTTPStatus.FORBIDDEN),
            ("drb", True, "test", None, HTTPStatus.FORBIDDEN),
            ("test_admin", False, None, None, HTTPStatus.BAD_REQUEST),
            ("test", False, "test", None, HTTPStatus.FORBIDDEN),
            (None, False, "drb", None, HTTPStatus.UNAUTHORIZED),
        ],
    )
    def test_empty_update(
        self,
        client,
        server_config,
        query_api,
        find_template,
        get_token_func,
        user,
        ao,
        owner,
        access,
        expected_status,
    ):
        """Check update with no Elasticsearch documents"""

        headers = None

        if user:
            token = get_token_func(user)
            assert token
            headers = {"authorization": f"bearer {token}"}

        drb = Dataset.query(name="drb")
        if ao:
            # Set archiveonly flag to disable index-map logic
            Metadata.setvalue(drb, Metadata.SERVER_ARCHIVE, True)
            index = None
        else:
            index = self.build_index_from_metadata()

        expected_owner = drb.owner_id
        expected_access = drb.access
        if owner and access:
            query = f"?owner={owner}&access={access}"
            expected_owner = owner
            expected_access = access
        elif owner:
            query = f"?owner={owner}"
            expected_owner = owner
        elif access:
            query = f"?access={access}"
            expected_access = access
        else:
            query = ""

        response = query_api(
            f"/datasets/random_md5_string1{query}",
            "/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=expected_status,
            request_method=ApiMethod.POST,
            json=EMPTY_DELDATE_RESPONSE,
            headers=headers,
        )
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
            assert expected_access == drb.access
            assert expected_owner == expected_owner
        else:
            # On failure, the dataset should still exist
            assert Dataset.query(name="drb")
            if expected_status == HTTPStatus.BAD_REQUEST:
                assert (
                    "Missing required parameters: access,owner"
                    == response.json["message"]
                )
            elif owner and not user:
                assert (
                    f"Requestor is unable to verify username {owner!r}"
                    == response.json["message"]
                )
            elif owner and user == "drb":
                assert (
                    "ADMIN role is required to change dataset ownership"
                    == response.json["message"]
                )
            else:
                assert response.json["message"].endswith(
                    "is not authorized to UPDATE a resource owned by drb with private access"
                )

    @pytest.mark.parametrize(
        "ao,hits",
        (
            (True, None),
            (False, None),
            (False, [{"a": "b", "c": 1}, {"a": "d", "c": 10}]),
        ),
    )
    def test_get(
        self,
        client,
        server_config,
        query_api,
        find_template,
        build_auth_header,
        ao,
        hits,
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

        json = copy.deepcopy(self.empty_es_response_payload)
        if hits and not ao:
            json["hits"]["total"]["value"] = len(hits)
            p_hits = hits.copy()
            for i, h in enumerate(p_hits):
                h["_id"] = i
            json["hits"]["hits"] = [
                {"_source": h, "_id": n} for n, h in enumerate(hits)
            ]
        else:
            p_hits = []

        response = query_api(
            self.pbench_endpoint,
            "/_search?ignore_unavailable=true",
            self.payload,
            index,
            expected_status,
            request_method=ApiMethod.GET,
            headers=build_auth_header["header"],
            json=json,
        )
        assert response.status_code == expected_status
        if expected_status == HTTPStatus.OK:
            assert p_hits == response.json
        elif expected_status == HTTPStatus.CONFLICT:
            assert {"message": "Dataset indexing was disabled"} == response.json
        else:
            assert {
                "message": "Unauthenticated client is not authorized to READ a resource owned by drb with private access"
            } == response.json
