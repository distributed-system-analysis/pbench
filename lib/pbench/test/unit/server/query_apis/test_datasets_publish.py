from http import HTTPStatus
from typing import Iterator

import elasticsearch
import pytest

from pbench.server import JSON
from pbench.server.database.models.dataset import Dataset
from pbench.server.globals import server
from pbench.test.unit.server.headertypes import HeaderTypes


class TestDatasetsPublish:
    """
    Unit testing for DatasetsPublish class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    PAYLOAD = {"access": "public"}

    def fake_elastic(self, monkeypatch, map: JSON, partial_fail: bool):
        """
        Pytest helper to install a mock for the Elasticsearch streaming_bulk
        helper API for testing.

        Args:
            monkeypatch: The monkeypatch fixture from the test case
            map: The generated document index map from the test case
            partial_fail: A boolean indicating whether some bulk operations
                should be marked as failures.

        Yields:
            Response documents from the mocked streaming_bulk helper
        """
        expected_results = []
        expected_ids = []

        for index in map:
            first = True
            for docid in map[index]:
                update = {
                    "_index": index,
                    "_type": "_doc",
                    "_id": docid,
                    "_version": 11,
                    "result": "noop",
                    "_shards": {"total": 2, "successful": 2, "failed": 0},
                    "_seq_no": 10,
                    "_primary_term": 3,
                    "status": 200,
                }
                if first and partial_fail:
                    status = False
                    first = False
                    update["error"] = {"reason": "Just kidding", "type": "KIDDING"}
                else:
                    status = True
                expected_results.append((status, {"update": update}))
                expected_ids.append(docid)

        def fake_bulk(
            elastic: elasticsearch.Elasticsearch,
            stream: Iterator[dict],
            raise_on_error: bool = True,
            raise_on_exception: bool = True,
        ):
            """
            Helper function to mock the Elasticsearch helper streaming_bulk API,
            which will validate the input actions and generate expected responses.

            Args:
                elastic: An Elasticsearch object
                stream: The input stream of bulk action dicts
                raise_on_error: indicates whether errors should be raised
                raise_on_exception: indicates whether exceptions should propagate
                    or be trapped

            Yields:
                Response documents from the mocked streaming_bulk helper
            """
            # Consume and validate the command generator
            for cmd in stream:
                assert cmd["_op_type"] == "update"
                assert cmd["_id"] in expected_ids

            # Generate a sequence of result documents more or less as we'd
            # expect to see from Elasticsearch
            for item in expected_results:
                yield item

        monkeypatch.setattr("elasticsearch.helpers.streaming_bulk", fake_bulk)

    @pytest.mark.parametrize(
        "owner",
        ("drb", "test"),
    )
    def test_query(
        self,
        attach_dataset,
        build_auth_header,
        client,
        get_document_map,
        monkeypatch,
        owner,
    ):
        """
        Check behavior of the publish API with various combinations of dataset
        owner (managed by the "owner" parametrization here) and authenticated
        user (managed by the build_auth_header fixture).
        """
        self.fake_elastic(monkeypatch, get_document_map, False)

        is_admin = build_auth_header["header_param"] == HeaderTypes.VALID_ADMIN
        if not HeaderTypes.is_valid(build_auth_header["header_param"]):
            expected_status = HTTPStatus.UNAUTHORIZED
        elif owner != "drb" and not is_admin:
            expected_status = HTTPStatus.FORBIDDEN
        else:
            expected_status = HTTPStatus.OK

        ds = Dataset.query(name=owner)

        response = client.post(
            f"{server.config.rest_uri}/datasets/publish/{ds.resource_id}",
            headers=build_auth_header["header"],
            query_string=self.PAYLOAD,
        )
        assert response.status_code == expected_status
        if expected_status == HTTPStatus.OK:
            assert response.json == {"ok": 31, "failure": 0}
            dataset = Dataset.query(name=owner)
            assert dataset.access == Dataset.PUBLIC_ACCESS

    def test_partial(
        self,
        attach_dataset,
        client,
        get_document_map,
        monkeypatch,
        pbench_token,
    ):
        """
        Check the publish API when some document updates fail. We expect an
        internal error with a report of success and failure counts.
        """
        self.fake_elastic(monkeypatch, get_document_map, True)

        response = client.post(
            f"{server.config.rest_uri}/datasets/publish/random_md5_string1",
            headers={"authorization": f"Bearer {pbench_token}"},
            query_string=self.PAYLOAD,
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json == {"ok": 28, "failure": 3}

        # Verify that the Dataset access didn't change
        dataset = Dataset.query(name="drb")
        assert dataset.access == Dataset.PRIVATE_ACCESS

    def test_no_dataset(self, client, get_document_map, monkeypatch, pbench_token):
        """
        Check the publish API if the dataset doesn't exist.
        """

        response = client.post(
            f"{server.config.rest_uri}/datasets/publish/badwolf",
            headers={"authorization": f"Bearer {pbench_token}"},
            query_string=self.PAYLOAD,
        )

        # Verify the report and status
        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.json["message"] == "Dataset 'badwolf' not found"

    def test_no_index(self, client, monkeypatch, attach_dataset, pbench_token):
        """
        Check the publish API if the dataset has no INDEX_MAP. It should
        fail with a CONFLICT error.
        """
        self.fake_elastic(monkeypatch, {}, True)

        ds = Dataset.query(name="drb")
        response = client.post(
            f"{server.config.rest_uri}/datasets/publish/{ds.resource_id}",
            headers={"authorization": f"Bearer {pbench_token}"},
            query_string=self.PAYLOAD,
        )

        # Verify the report and status
        assert response.status_code == HTTPStatus.CONFLICT
        assert response.json == {
            "message": "Dataset update requires 'Indexed' dataset but state is 'Indexed'"
        }

    def test_exception(
        self,
        attach_dataset,
        client,
        monkeypatch,
        get_document_map,
        pbench_token,
        capinternal,
    ):
        """
        Check the publish API response if the bulk helper throws an exception.

        (It shouldn't do this as we've set raise_on_exception=False, but we
        check the code path anyway.)
        """

        def fake_bulk(
            elastic: elasticsearch.Elasticsearch,
            stream: Iterator[dict],
            raise_on_error: bool = True,
            raise_on_exception: bool = True,
        ):
            raise elasticsearch.helpers.BulkIndexError("test")

        monkeypatch.setattr("elasticsearch.helpers.streaming_bulk", fake_bulk)

        response = client.post(
            f"{server.config.rest_uri}/datasets/publish/random_md5_string1",
            headers={"authorization": f"Bearer {pbench_token}"},
            query_string=self.PAYLOAD,
        )

        # Verify the failure
        capinternal("Unexpected backend error", response)
