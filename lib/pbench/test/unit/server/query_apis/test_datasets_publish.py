from http import HTTPStatus
from typing import Iterator

import elasticsearch
import pytest

from pbench.server.api.resources import JSON
from pbench.server.database.models.datasets import Dataset
from pbench.test.unit.server.headertypes import HeaderTypes


class TestDatasetsPublish:
    """
    Unit testing for DatasetsPublish class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    PAYLOAD = {"controller": "node", "name": "drb", "access": "public"}

    def fake_elastic(self, monkeypatch, map: JSON, partial_fail: bool):
        """
        Helper function to mock the Elasticsearch helper streaming_bulk API,
        which will validate the input actions and generate expected responses.

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
                item = {"update": update}
                expected_results.append((status, item))
                expected_ids.append(docid)

        def fake_bulk(
            elastic: elasticsearch.Elasticsearch,
            stream: Iterator[dict],
            raise_on_error: bool = True,
            raise_on_exception: bool = True,
        ):
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
        "owner", ("drb", "test"),
    )
    def test_query(
        self,
        attach_dataset,
        build_auth_header,
        client,
        get_document_map,
        monkeypatch,
        owner,
        server_config,
    ):
        """
        Check behavior of the publish API with various combinations of dataset
        owner (managed by the "owner" parametrization here) and authenticated
        user (managed by the build_auth_header fixture).
        """
        self.fake_elastic(monkeypatch, get_document_map, False)

        if (
            owner == "no_user"
            or HeaderTypes.is_valid(build_auth_header["header_param"])
        ) and owner != "badwolf":
            expected_status = HTTPStatus.OK
        else:
            expected_status = HTTPStatus.FORBIDDEN

        response = client.post(
            f"{server_config.rest_uri}/datasets/publish",
            headers=build_auth_header["header"],
            json=self.PAYLOAD,
        )
        assert response.status_code == expected_status
        if expected_status == HTTPStatus.OK:
            assert response.json == {"ok": 31}
            dataset = Dataset.attach(controller="node", name="drb")
            assert dataset.access == Dataset.PUBLIC_ACCESS

    def test_partial(
        self,
        attach_dataset,
        client,
        get_document_map,
        monkeypatch,
        pbench_token,
        server_config,
    ):
        """
        Check the publish API when some document updates fail. We expect an
        internal error with a report of success and failure counts.
        """
        self.fake_elastic(monkeypatch, get_document_map, True)

        response = client.post(
            f"{server_config.rest_uri}/datasets/publish",
            headers={"authorization": f"Bearer {pbench_token}"},
            json=self.PAYLOAD,
        )

        # Verify the report and status
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert response.json["data"] == {"ok": 28, "KIDDING": 3}

        # Verify that the Dataset access didn't change
        dataset = Dataset.attach(controller="node", name="drb")
        assert dataset.access == Dataset.PRIVATE_ACCESS

    def test_no_dataset(
        self, client, get_document_map, monkeypatch, pbench_token, server_config
    ):
        """
        Check the publish API if the dataset doesn't exist.
        """
        payload = self.PAYLOAD.copy()
        payload["name"] = "badwolf"

        response = client.post(
            f"{server_config.rest_uri}/datasets/publish",
            headers={"authorization": f"Bearer {pbench_token}"},
            json=payload,
        )

        # Verify the report and status
        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.json["message"] == "No dataset node|badwolf"

    def test_exception(
        self, attach_dataset, client, monkeypatch, pbench_token, server_config
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
            raise elasticsearch.helpers.BulkIndexError

        monkeypatch.setattr("elasticsearch.helpers.streaming_bulk", fake_bulk)

        response = client.post(
            f"{server_config.rest_uri}/datasets/publish",
            headers={"authorization": f"Bearer {pbench_token}"},
            json=self.PAYLOAD,
        )

        # Verify the failure
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert response.json["message"] == "INTERNAL ERROR"
