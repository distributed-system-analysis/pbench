import copy
from http import HTTPStatus

import pytest

from pbench.server import OperationCode
from pbench.server.api.resources import ApiMethod
from pbench.server.api.resources.query_apis.datasets.datasets import Datasets
from pbench.server.database.models.audit import Audit, AuditStatus, AuditType
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetNotFound,
    Metadata,
    Operation,
    OperationName,
    OperationState,
)
from pbench.server.database.models.users import User
from pbench.server.sync import Sync
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
        query_api,
        user,
        ao,
        expected_status,
        get_token_func,
    ):
        """Check deletion with no Elasticsearch documents"""

        headers = None

        if user:
            user_id = User.query(username=user).id
            token = get_token_func(user)
            assert token
            headers = {"authorization": f"bearer {token}"}
        else:
            user_id = None

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
            expect_call=(expected_status == HTTPStatus.OK and not ao),
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
            audit = Audit.query()
            assert len(audit) == 2
            assert audit[0].id == 1
            assert audit[0].root_id is None
            assert audit[0].operation == OperationCode.DELETE
            assert audit[0].status == AuditStatus.BEGIN
            assert audit[0].name == "delete"
            assert audit[0].object_type == AuditType.DATASET
            assert audit[0].object_id == "random_md5_string1"
            assert audit[0].object_name == "drb"
            assert audit[0].user_id == user_id
            assert audit[0].user_name == user
            assert audit[0].reason is None
            assert audit[0].attributes is None
            assert audit[1].id == 2
            assert audit[1].root_id == 1
            assert audit[1].operation == OperationCode.DELETE
            assert audit[1].status == AuditStatus.SUCCESS
            assert audit[1].name == "delete"
            assert audit[1].object_type == AuditType.DATASET
            assert audit[1].object_id == "random_md5_string1"
            assert audit[1].object_name == "drb"
            assert audit[1].user_id == user_id
            assert audit[1].user_name == user
            assert audit[1].reason is None
            assert audit[1].attributes == {"results": expected}

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
    def test_update(
        self,
        client,
        query_api,
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
            user_id = User.query(username=user).id
            token = get_token_func(user)
            assert token
            headers = {"authorization": f"bearer {token}"}
        else:
            user_id = None

        drb = Dataset.query(name="drb")
        if ao:
            # Set archiveonly flag to disable index-map logic
            Metadata.setvalue(drb, Metadata.SERVER_ARCHIVE, True)
            index = None
        else:
            index = self.build_index_from_metadata()

        expected_owner = drb.owner_id
        original_owner = drb.owner_id
        expected_access = drb.access
        original_access = drb.access
        audit_attr = {}
        if owner and access:
            query = f"?owner={owner}&access={access}"
            o_id = User.query(username=owner).id
            expected_owner = owner
            expected_access = access
            audit_attr = {"owner": o_id, "access": access}
        elif owner:
            query = f"?owner={owner}"
            o_id = User.query(username=owner).id
            expected_owner = owner
            audit_attr = {"owner": o_id}
        elif access:
            query = f"?access={access}"
            expected_access = access
            audit_attr = {"access": access}
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
            expect_call=(expected_status == HTTPStatus.OK and not ao),
        )

        # Look up the post-update dataset
        drb = Dataset.query(name="drb")

        if response.status_code == HTTPStatus.OK:
            assert expected_access == drb.access
            assert expected_owner == expected_owner
            res_json = response.json
            expected = {
                "total": 0,
                "updated": 0,
                "deleted": 0,
                "failures": 0,
                "version_conflicts": 0,
            }
            assert expected == res_json

            audit_attr["results"] = expected
            audit = Audit.query()
            assert len(audit) == 2
            assert audit[0].id == 1
            assert audit[0].root_id is None
            assert audit[0].operation == OperationCode.UPDATE
            assert audit[0].status == AuditStatus.BEGIN
            assert audit[0].name == "update"
            assert audit[0].object_type == AuditType.DATASET
            assert audit[0].object_id == "random_md5_string1"
            assert audit[0].object_name == "drb"
            assert audit[0].user_id == user_id
            assert audit[0].user_name == user
            assert audit[0].reason is None
            assert audit[0].attributes is None
            assert audit[1].id == 2
            assert audit[1].root_id == 1
            assert audit[1].operation == OperationCode.UPDATE
            assert audit[1].status == AuditStatus.SUCCESS
            assert audit[1].name == "update"
            assert audit[1].object_type == AuditType.DATASET
            assert audit[1].object_id == "random_md5_string1"
            assert audit[1].object_name == "drb"
            assert audit[1].user_id == user_id
            assert audit[1].user_name == user
            assert audit[1].reason is None
            assert audit[1].attributes == audit_attr
        else:
            assert original_access == drb.access
            assert original_owner == drb.owner_id
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

    def test_update_partial_failure(self, client, query_api, get_token_func):
        """Check update with no Elasticsearch documents"""

        headers = None

        token = get_token_func("drb")
        assert token
        headers = {"authorization": f"bearer {token}"}
        index = self.build_index_from_metadata()

        es_json = {
            "took": 42,
            "timed_out": False,
            "total": 2,
            "updated": 1,
            "deleted": 0,
            "batches": 0,
            "version_conflicts": 0,
            "noops": 0,
            "retries": {"bulk": 0, "search": 0},
            "throttled_millis": 0,
            "requests_per_second": 0.0,
            "throttled_until_millis": 0,
            "failures": ["bad"],
        }
        response = query_api(
            "/datasets/random_md5_string1?access=public",
            "/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=HTTPStatus.OK,
            request_method=ApiMethod.POST,
            json=es_json,
            headers=headers,
            expect_call=True,
        )
        expected = {
            "total": 2,
            "updated": 1,
            "deleted": 0,
            "failures": 1,
            "version_conflicts": 0,
        }
        assert expected == response.json

    def test_update_total_failure(self, client, query_api, get_token_func):
        """Check update with no Elasticsearch documents"""

        headers = None

        token = get_token_func("drb")
        assert token
        headers = {"authorization": f"bearer {token}"}
        index = self.build_index_from_metadata()

        es_json = {
            "took": 42,
            "timed_out": False,
            "total": 2,
            "deleted": 0,
            "batches": 0,
            "version_conflicts": 0,
            "noops": 0,
            "retries": {"bulk": 0, "search": 0},
            "throttled_millis": 0,
            "requests_per_second": 0.0,
            "throttled_until_millis": 0,
            "failures": ["bad", "me too"],
        }
        query_api(
            "/datasets/random_md5_string1?access=public",
            "/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=HTTPStatus.INTERNAL_SERVER_ERROR,
            request_method=ApiMethod.POST,
            json=es_json,
            headers=headers,
            expect_call=True,
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
        query_api,
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
        if expected_status == HTTPStatus.OK:
            assert p_hits == response.json
        elif expected_status == HTTPStatus.CONFLICT:
            assert {"message": "Dataset indexing was disabled"} == response.json
        else:
            assert {
                "message": "Unauthenticated client is not authorized to READ a resource owned by drb with private access"
            } == response.json

    @pytest.mark.parametrize("value", (None, "not-integer"))
    def test_bad_get(self, client, query_api, get_token_func, value):
        """Check update with no Elasticsearch documents"""

        token = get_token_func("drb")
        assert token
        headers = {"authorization": f"bearer {token}"}
        index = self.build_index_from_metadata()

        json = {
            "took": 1,
            "timed_out": False,
            "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 0, "relation": "eq"},
                "max_score": None,
                "hits": [],
            },
        }
        if value:
            json["hits"]["total"]["value"] = value
        else:
            del json["hits"]["total"]["value"]
        query_api(
            self.pbench_endpoint,
            "/_search?ignore_unavailable=true",
            self.payload,
            index,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            request_method=ApiMethod.GET,
            headers=headers,
            json=json,
            expect_call=True,
        )

    def test_update_unstable(self, monkeypatch, client, query_api, get_token_func):
        """Check update on a dataset with in-progress operations"""

        token = get_token_func("drb")
        assert token
        headers = {"authorization": f"bearer {token}"}
        index = self.build_index_from_metadata()

        monkeypatch.setattr(
            Operation,
            "by_state",
            lambda _d, _s: [
                Operation(name=OperationName.INDEX, state=OperationState.WORKING)
            ],
        )

        response = query_api(
            "/datasets/random_md5_string1?access=public",
            "/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=HTTPStatus.CONFLICT,
            request_method=ApiMethod.POST,
            json=EMPTY_DELDATE_RESPONSE,
            headers=headers,
        )

        assert {"message": "Dataset is working on INDEX"} == response.json

    def test_update_bad_first_sync(
        self, monkeypatch, client, query_api, get_token_func
    ):
        """Check update when we're unable to update to WORKING state"""

        token = get_token_func("drb")
        assert token
        headers = {"authorization": f"bearer {token}"}
        index = self.build_index_from_metadata()

        def fails(_self, _dataset, _state):
            raise Exception("I'm broken")

        monkeypatch.setattr(Sync, "update", fails)

        query_api(
            "/datasets/random_md5_string1?access=public",
            "/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=HTTPStatus.INTERNAL_SERVER_ERROR,
            request_method=ApiMethod.POST,
            json=EMPTY_DELDATE_RESPONSE,
            headers=headers,
        )

    def test_update_bad_final_sync(
        self, monkeypatch, client, query_api, get_token_func
    ):
        """Check update when we're unable to finalize the operational state"""

        token = get_token_func("drb")
        assert token
        headers = {"authorization": f"bearer {token}"}
        index = self.build_index_from_metadata()

        def fails(
            _s, dataset: Dataset, state: OperationState, enabled=None, message=None
        ):
            if state is not OperationState.WORKING:
                raise Exception("I'm broken")

        monkeypatch.setattr(Sync, "update", fails)

        query_api(
            "/datasets/random_md5_string1?access=public",
            "/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=HTTPStatus.INTERNAL_SERVER_ERROR,
            request_method=ApiMethod.POST,
            json=EMPTY_DELDATE_RESPONSE,
            headers=headers,
            expect_call=True,
        )

    def test_update_bad_update(self, monkeypatch, client, query_api, get_token_func):
        """Check update when we're unable to update the Dataset"""

        token = get_token_func("drb")
        assert token
        headers = {"authorization": f"bearer {token}"}
        index = self.build_index_from_metadata()

        def fails(_s):
            raise Exception("I'm broken")

        monkeypatch.setattr(Dataset, "update", fails)

        query_api(
            "/datasets/random_md5_string1?access=public",
            "/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=HTTPStatus.INTERNAL_SERVER_ERROR,
            request_method=ApiMethod.POST,
            json=EMPTY_DELDATE_RESPONSE,
            headers=headers,
            expect_call=True,
        )

    def test_update_bad_delete(self, monkeypatch, client, query_api, get_token_func):
        """Check update when we're unable to delete the Dataset"""

        token = get_token_func("drb")
        assert token
        headers = {"authorization": f"bearer {token}"}
        index = self.build_index_from_metadata()

        def fails(_s):
            raise Exception("I'm broken")

        monkeypatch.setattr(Dataset, "delete", fails)

        query_api(
            "/datasets/random_md5_string1",
            "/_delete_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=HTTPStatus.INTERNAL_SERVER_ERROR,
            request_method=ApiMethod.DELETE,
            json=EMPTY_DELDATE_RESPONSE,
            headers=headers,
            expect_call=True,
        )
