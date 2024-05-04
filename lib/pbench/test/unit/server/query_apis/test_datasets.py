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
from pbench.server.database.models.index_map import IndexMap
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
        "user,ao,idx,expected_status",
        [
            ("drb", False, True, HTTPStatus.OK),
            ("drb", False, False, HTTPStatus.OK),
            ("drb", True, True, HTTPStatus.OK),
            ("drb", True, False, HTTPStatus.OK),
            ("test_admin", False, True, HTTPStatus.OK),
            ("test_admin", False, False, HTTPStatus.OK),
            ("test", False, False, HTTPStatus.FORBIDDEN),
            (None, False, False, HTTPStatus.UNAUTHORIZED),
        ],
    )
    def test_empty_delete(
        self,
        client,
        query_api,
        user,
        ao,
        idx,
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

        drb = Dataset.query(name="drb")
        index = None
        if ao:
            # Set archiveonly flag to disable index-map logic
            Metadata.setvalue(drb, Metadata.SERVER_ARCHIVE, True)

        # If we want an index, build the expected path; otherwise make sure
        # the dataset doesn't have one.
        if idx:
            index = self.build_index_from_metadata()
        else:
            IndexMap.delete(drb)

        expect_a_call = expected_status == HTTPStatus.OK and idx
        response = query_api(
            pbench_uri=self.pbench_endpoint,
            es_uri=self.elastic_endpoint,
            payload=None,
            expected_index=index,
            expected_status=expected_status,
            headers=headers,
            request_method=self.api_method,
            expect_call=expect_a_call,
            json=EMPTY_DELDATE_RESPONSE,
        )
        if response.status_code == HTTPStatus.OK:
            expected = {
                "total": 0,
                "updated": 0,
                "deleted": 0,
                "failures": 0,
                "version_conflicts": 0,
            }
            assert expected == response.json
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
            Dataset.query(name="drb")
            assert response.json["message"].endswith(
                "is not authorized to DELETE a resource owned by drb with private access"
            )

            # permission errors should be caught before auditing
            assert len(Audit.query()) == 0

    @pytest.mark.parametrize(
        "user,ao,idx,owner,access,expected_status",
        [
            ("drb", False, True, None, "public", HTTPStatus.OK),
            ("drb", False, False, None, "public", HTTPStatus.OK),
            ("drb", True, True, None, "public", HTTPStatus.OK),
            ("test_admin", False, True, "test", None, HTTPStatus.OK),
            ("test", False, True, None, "public", HTTPStatus.FORBIDDEN),
            (None, False, True, None, "public", HTTPStatus.UNAUTHORIZED),
            ("drb", False, True, "test", "public", HTTPStatus.FORBIDDEN),
            ("drb", True, True, "test", None, HTTPStatus.FORBIDDEN),
            ("test_admin", False, True, None, None, HTTPStatus.BAD_REQUEST),
            ("test", False, True, "test", None, HTTPStatus.FORBIDDEN),
            (None, False, True, "drb", None, HTTPStatus.UNAUTHORIZED),
        ],
    )
    def test_update(
        self,
        client,
        query_api,
        get_token_func,
        user,
        ao,
        idx,
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
        index = None
        if ao:
            # Set archiveonly flag to disable index-map logic
            Metadata.setvalue(drb, Metadata.SERVER_ARCHIVE, True)

        # If we want an index, build the expected path; otherwise make sure
        # the dataset doesn't have one.
        if idx:
            index = self.build_index_from_metadata()
        else:
            IndexMap.delete(drb)

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

        expect_a_call = expected_status == HTTPStatus.OK and idx
        response = query_api(
            pbench_uri=f"/datasets/random_md5_string1{query}",
            es_uri="/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=expected_status,
            headers=headers,
            request_method=ApiMethod.POST,
            expect_call=expect_a_call,
            json=EMPTY_DELDATE_RESPONSE,
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
        """Check update with partial Elasticsearch failure"""

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
            pbench_uri="/datasets/random_md5_string1?access=public",
            es_uri="/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=HTTPStatus.OK,
            headers=headers,
            request_method=ApiMethod.POST,
            expect_call=True,
            json=es_json,
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
        """Check update with all Elasticsearch operations failing"""

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
            pbench_uri="/datasets/random_md5_string1?access=public",
            es_uri="/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=HTTPStatus.INTERNAL_SERVER_ERROR,
            headers=headers,
            request_method=ApiMethod.POST,
            expect_call=True,
            json=es_json,
        )

    @pytest.mark.parametrize(
        "ao,idx", ((True, True), (True, False), (False, True), (False, False))
    )
    def test_get(
        self, monkeypatch, more_datasets, client, query_api, build_auth_header, ao, idx
    ):
        """Check on the GET summary behavior

        We should report a JSON document with an integer count for each index
        name.

        We test with and without "archiveonly" set as well as with various
        authentication scenarios through the build_auth_header fixture.
        """
        auth_json = {"user": "drb", "access": "private"}

        expected_status = self.get_expected_status(
            auth_json, build_auth_header["header_param"]
        )

        ds = Dataset.query(name="drb")
        json = copy.deepcopy(self.empty_es_response_payload)
        index = None
        if ao:
            # Set archiveonly flag to disable index-map logic
            Metadata.setvalue(ds, Metadata.SERVER_ARCHIVE, True)

        expected = {}
        if idx:
            indices = IndexMap.indices(ds)
            index = "/" + ",".join(indices)
            hits = []
            for i, n in enumerate(indices):
                hits.append({"_index": n, "_id": i, "_source": {"data": f"{n}_{i}"}})
                expected[n] = 1
            json["hits"]["total"]["value"] = len(hits)
            json["hits"]["hits"] = hits
        else:
            IndexMap.delete(ds)

        expect_a_call = expected_status == HTTPStatus.OK and idx
        response = query_api(
            pbench_uri=self.pbench_endpoint,
            es_uri="/_search?ignore_unavailable=true",
            payload=self.payload,
            expected_index=index,
            expected_status=expected_status,
            headers=build_auth_header["header"],
            request_method=ApiMethod.GET,
            expect_call=expect_a_call,
            json=json,
        )
        if expected_status == HTTPStatus.OK:
            assert expected == response.json
        else:
            assert {
                "message": "Unauthenticated client is not authorized to READ a resource owned by drb with private access"
            } == response.json

    @pytest.mark.parametrize("hits", (None, 0, "string", {}))
    def test_bad_get(self, client, query_api, get_token_func, hits):
        """Check a GET with bad Elasticsearch hit counts"""

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
        if hits is None:
            del json["hits"]["hits"]
        else:
            json["hits"]["hits"] = hits
        query_api(
            pbench_uri=self.pbench_endpoint,
            es_uri="/_search?ignore_unavailable=true",
            payload=self.payload,
            expected_index=index,
            expected_status=HTTPStatus.INTERNAL_SERVER_ERROR,
            headers=headers,
            request_method=ApiMethod.GET,
            expect_call=True,
            json=json,
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
            pbench_uri="/datasets/random_md5_string1?access=public",
            es_uri="/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=HTTPStatus.CONFLICT,
            headers=headers,
            request_method=ApiMethod.POST,
            json=EMPTY_DELDATE_RESPONSE,
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
            pbench_uri="/datasets/random_md5_string1?access=public",
            es_uri="/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=HTTPStatus.INTERNAL_SERVER_ERROR,
            headers=headers,
            request_method=ApiMethod.POST,
            json=EMPTY_DELDATE_RESPONSE,
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
            pbench_uri="/datasets/random_md5_string1?access=public",
            es_uri="/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=HTTPStatus.INTERNAL_SERVER_ERROR,
            headers=headers,
            request_method=ApiMethod.POST,
            expect_call=True,
            json=EMPTY_DELDATE_RESPONSE,
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
            pbench_uri="/datasets/random_md5_string1?access=public",
            es_uri="/_update_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=HTTPStatus.INTERNAL_SERVER_ERROR,
            headers=headers,
            request_method=ApiMethod.POST,
            expect_call=True,
            json=EMPTY_DELDATE_RESPONSE,
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
            pbench_uri="/datasets/random_md5_string1",
            es_uri="/_delete_by_query?ignore_unavailable=true&refresh=true",
            payload=None,
            expected_index=index,
            expected_status=HTTPStatus.INTERNAL_SERVER_ERROR,
            headers=headers,
            request_method=ApiMethod.DELETE,
            expect_call=True,
            json=EMPTY_DELDATE_RESPONSE,
        )
