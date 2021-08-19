import json
import pytest
import requests
from http import HTTPStatus
from pbench.server.api.resources.query_apis.datasets_publish import DatasetsPublish
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.server.database.models.users import User
from pbench.test.unit.server.query_apis.commons import Commons


@pytest.fixture()
def attach_dataset(monkeypatch, pbench_token, create_user):
    """
    Mock a Dataset attach call to return an object. We mock the Dataset.attach
    method to avoid DB access here, however the user authentication mechanism
    is not yet mocked so we have to look up User data.

    Args:
        monkeypatch: patching fixture
        pbench_token: create a "drb" user for testing
        create_user: create a "test" user
    """
    datasets = {}
    drb = User.query(username="drb")  # Created by pbench_token fixture
    test = User.query(username="test")  # Created by create_user fixture
    datasets["drb"] = Dataset(
        owner=drb,
        owner_id=drb.id,
        controller="node",
        name="drb",
        access="private",
        id=1,
    )
    datasets["test"] = Dataset(
        owner=test,
        owner_id=test.id,
        controller="node",
        name="test",
        access="private",
        id=2,
    )

    def attach_dataset(controller: str, name: str) -> Dataset:
        return datasets[name]

    with monkeypatch.context() as m:
        m.setattr(Dataset, "attach", attach_dataset)
        yield


@pytest.fixture()
def get_document_map(monkeypatch, attach_dataset):
    """
    Mock a Metadata get call to return an Elasticsearch document index
    without requiring a DB query.

    Args:
        monkeypatch: patching fixture
        attach_dataset:  create a mock Dataset object
    """
    map = Metadata(
        key=Metadata.INDEX_MAP,
        value=json.dumps(
            {
                "run-data.2021-06": ["a suitably long MD5", "another long MD5"],
                "run-toc.2021-06": ["another long MD5", "one more long MD5"],
            }
        ),
    )

    def get_document_map(dataset: Dataset, key: str) -> Metadata:
        return map

    with monkeypatch.context() as m:
        m.setattr(Metadata, "get", get_document_map)
        yield map


class TestDatasetsPublish(Commons):
    """
    Unit testing for DatasetsPublish class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        super()._setup(
            cls_obj=DatasetsPublish(client.config, client.logger),
            pbench_endpoint="/datasets/publish",
            elastic_endpoint="/_bulk?refresh=true",
            payload={"controller": "node", "name": "drb", "access": "public"},
        )

    @pytest.mark.parametrize(
        "owner", ("drb", "test"),
    )
    def test_query(
        self,
        server_config,
        query_api,
        user_ok,
        get_document_map,
        build_auth_header,
        owner,
    ):
        """
        Check the construction of Elasticsearch query URI and filtering of the
        response body. Note that the mock set up by the attach_dataset fixture
        matches the dataset name to the dataset's owner, so we use the username
        as the "name" key below. The authenticated caller is always "drb", so
        we expect access to the "test" dataset to fail with a permission error.
        """
        self.payload["name"] = owner
        map = json.loads(get_document_map.value)
        items = []

        for index in map:
            for docid in map[index]:
                item = {
                    "update": {
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
                }
                items.append(item)

        response_payload = {
            "took": 16,
            "errors": False,
            "items": items,
        }

        if build_auth_header["header_param"] == "valid" and owner == "drb":
            expected_status = HTTPStatus.OK
        else:
            expected_status = HTTPStatus.FORBIDDEN

        response = query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.payload,
            "",
            expected_status,
            json=response_payload,
            status=HTTPStatus.OK,
            headers=build_auth_header["header"],
        )
        summary = response.get_json(force=True)
        if expected_status == HTTPStatus.OK:
            assert summary == {"ok": 4}
        else:
            assert summary == {"message": "Not Authorized"}

    def test_partial_success(
        self, client, server_config, query_api, user_ok, get_document_map, pbench_token,
    ):
        """
        Check the handling of a query that doesn't completely succeed.
        """
        items = []
        first = True
        map = json.loads(get_document_map.value)
        for index in map:
            for docid in map[index]:
                item = {
                    "update": {
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
                }
                if first:
                    first = False
                    u = item["update"]
                    u["error"] = {
                        "type": "document_missing_exception",
                        "reason": "[_doc][6]: document missing",
                        "index_uuid": "aAsFqTI0Tc2W0LCWgPNrOA",
                        "shard": "0",
                        "index": index,
                    }
                    u["status"] = 400

                items.append(item)

        response_payload = {
            "took": 16,
            "errors": True,
            "items": items,
        }

        response = query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.payload,
            "",
            HTTPStatus.INTERNAL_SERVER_ERROR,
            json=response_payload,
            headers={"Authorization": "Bearer " + pbench_token},
        )
        response_doc = response.get_json(force=True)
        message = response_doc["message"]
        assert message == (
            "DatasetsPublish: the query postprocessor was unable to complete: "
            "Postprocessing error returning 500: '1 of 4 Elasticsearch document UPDATE operations failed "
            "[{'document_missing_exception': 1, 'ok': 3}]'"
        )
        summary = response_doc["data"]
        assert summary == {"ok": 3, "document_missing_exception": 1}

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
        ),
    )
    def test_http_exception(
        self,
        client,
        server_config,
        query_api,
        exceptions,
        user_ok,
        find_template,
        get_document_map,
        pbench_token,
    ):
        """
        Check that an exception in calling Elasticsearch is reported correctly.
        """
        query_api(
            "/datasets/publish",
            "/_bulk?refresh=true",
            self.payload,
            "",
            exceptions["status"],
            body=exceptions["exception"],
            headers={"Authorization": "Bearer " + pbench_token},
        )

    @pytest.mark.parametrize("errors", (400, 500, 409))
    def test_http_error(
        self,
        server_config,
        query_api,
        errors,
        user_ok,
        find_template,
        get_document_map,
        pbench_token,
    ):
        """
        Check that an Elasticsearch error is reported correctly through the
        response.raise_for_status() and Pbench handlers.
        """
        query_api(
            "/datasets/publish",
            "/_bulk?refresh=true",
            self.payload,
            "",
            HTTPStatus.BAD_GATEWAY,
            status=errors,
            headers={"Authorization": "Bearer " + pbench_token},
        )
