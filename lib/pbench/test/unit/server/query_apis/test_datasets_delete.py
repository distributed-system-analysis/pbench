from http import HTTPStatus
from logging import Logger
from typing import Iterator

import elasticsearch
import pytest

from pbench.server import PbenchServerConfig
from pbench.server.filetree import FileTree
from pbench.server.api.resources import JSON
from pbench.server.database.models.datasets import Dataset, DatasetNotFound
from pbench.test.unit.server.headertypes import HeaderTypes


class TestDatasetsDelete:
    """
    Unit testing for DatasetsDelete class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    PAYLOAD = {"name": "drb"}
    tarball_deleted = None

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
                delete = {
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
                    delete["error"] = {"reason": "Just kidding", "type": "KIDDING"}
                else:
                    status = True
                item = {"delete": delete}
                expected_results.append((status, item))
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
                assert cmd["_op_type"] == "delete"
                assert cmd["_id"] in expected_ids

            # Generate a sequence of result documents more or less as we'd
            # expect to see from Elasticsearch
            for item in expected_results:
                yield item

        monkeypatch.setattr("elasticsearch.helpers.streaming_bulk", fake_bulk)

    def fake_filetree(self, monkeypatch):
        def fake_constructor(self, options: PbenchServerConfig, logger: Logger):
            pass

        def fake_delete(self, name: str) -> None:
            TestDatasetsDelete.tarball_deleted = name

        TestDatasetsDelete.tarball_deleted = None
        monkeypatch.setattr(FileTree, "__init__", fake_constructor)
        monkeypatch.setattr(FileTree, "delete", fake_delete)

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
        self.fake_filetree(monkeypatch)
        payload = self.PAYLOAD.copy()
        payload["name"] = owner

        is_admin = build_auth_header["header_param"] == HeaderTypes.VALID_ADMIN
        if not HeaderTypes.is_valid(build_auth_header["header_param"]):
            expected_status = HTTPStatus.UNAUTHORIZED
        elif owner != "drb" and not is_admin:
            expected_status = HTTPStatus.FORBIDDEN
        else:
            expected_status = HTTPStatus.OK

        response = client.post(
            f"{server_config.rest_uri}/datasets/delete",
            headers=build_auth_header["header"],
            json=payload,
        )
        assert response.status_code == expected_status
        if expected_status == HTTPStatus.OK:
            assert response.json == {"ok": 31, "failure": 0}
            assert TestDatasetsDelete.tarball_deleted == owner

            # On success, the Dataset should be gone
            with pytest.raises(DatasetNotFound):
                Dataset.query(name=owner)
        else:
            # On failure, the Dataset should remain
            assert TestDatasetsDelete.tarball_deleted is None
            Dataset.query(name=owner)

    def test_partial(
        self,
        attach_dataset,
        caplog,
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
        self.fake_filetree(monkeypatch)

        response = client.post(
            f"{server_config.rest_uri}/datasets/delete",
            headers={"authorization": f"Bearer {pbench_token}"},
            json=self.PAYLOAD,
        )

        # Verify the report and status
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert response.json["data"] == {"ok": 28, "failure": 3}
        for record in caplog.records:
            if (
                record.levelname == "ERROR"
                and record.name == "pbench.server.api:__init__.py"
            ):
                assert (
                    record.message
                    == "DatasetsDelete:dataset drb(1)|node|drb: 28 successful document updates and 3 failures: defaultdict(<class 'collections.Counter'>, {'Just kidding': Counter({'unit-test.v6.run-data.2021-06': 1, 'unit-test.v6.run-toc.2021-06': 1, 'unit-test.v5.result-data-sample.2021-06': 1}), 'ok': Counter({'unit-test.v5.result-data-sample.2021-06': 19, 'unit-test.v6.run-toc.2021-06': 9})})"
                )

        # Verify that the Dataset still exists
        Dataset.query(controller="node", name="drb")

    def test_no_dataset(
        self, client, get_document_map, monkeypatch, pbench_token, server_config
    ):
        """
        Check the publish API if the dataset doesn't exist.
        """
        payload = self.PAYLOAD.copy()
        payload["name"] = "badwolf"

        response = client.post(
            f"{server_config.rest_uri}/datasets/delete",
            headers={"authorization": f"Bearer {pbench_token}"},
            json=payload,
        )

        # Verify the report and status
        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.json["message"] == "No dataset name=badwolf"

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
            f"{server_config.rest_uri}/datasets/delete",
            headers={"authorization": f"Bearer {pbench_token}"},
            json=self.PAYLOAD,
        )

        # Verify the failure
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert response.json["message"] == "INTERNAL ERROR"
