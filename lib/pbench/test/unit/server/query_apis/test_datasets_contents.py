from http import HTTPStatus

import pytest

from pbench.server.api.resources.query_apis.datasets.datasets_contents import (
    DatasetsContents,
)
from pbench.server.database.models.datasets import Dataset
from pbench.test.unit.server.query_apis.commons import Commons


class TestDatasetsContents(Commons):
    """
    Unit testing for DatasetsContents class.
    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        super()._setup(
            cls_obj=DatasetsContents(client.config, client.logger),
            pbench_endpoint="/datasets/contents",
            elastic_endpoint="/_search",
            payload={"run_id": "random_md5_string1", "parent": "/1-default"},
            index_from_metadata="run-toc",
        )

    def test_with_no_index_document(self, client, server_config):
        """
        Check the DatasetsContents API when no index name is provided
        """
        # remove the last component of the pbench_endpoint
        incorrect_endpoint = "/".join(self.pbench_endpoint.split("/")[:-1])
        response = client.get(f"{server_config.rest_uri}{incorrect_endpoint}")
        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_with_incorrect_index_document(self, client, server_config, pbench_token):
        """
        Check the Contents API when an incorrect index name is provided.
        """
        incorrect_endpoint = "/".join(self.pbench_endpoint.split("/")[:-1]) + "/test"
        response = client.post(
            f"{server_config.rest_uri}{incorrect_endpoint}",
            headers={"Authorization": "Bearer " + pbench_token},
            json=self.payload,
        )
        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_query(
        self,
        server_config,
        query_api,
        pbench_token,
        build_auth_header,
        find_template,
        provide_metadata,
    ):
        """
        Check the construction of Elasticsearch query URI and filtering of the
        response body. Note that the mock set up by the attach_dataset fixture
        matches the dataset name to the dataset's owner.
        """
        response_payload = {
            "took": 7,
            "timed_out": False,
            "_shards": {"total": 3, "successful": 3, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "max_score": 0.0,
                "hits": [
                    {
                        "_index": "riya-pbench.v6.run-toc.2021-05",
                        "_type": "_doc",
                        "_id": "d4a8cc7c4ecef7vshg4tjhrew174828d",
                        "_score": 0.0,
                        "_source": {
                            "parent": "/",
                            "directory": "/1-default",
                            "mtime": "2021-05-01T24:00:00",
                            "mode": "0o755",
                            "name": "1-default",
                            "files": [
                                {
                                    "name": "reference-result",
                                    "mtime": "2021-05-01T24:00:00",
                                    "size": 0,
                                    "mode": "0o777",
                                    "type": "sym",
                                    "linkpath": "sample1",
                                }
                            ],
                            "run_data_parent": "ece030bdgfkjasdkf7435e6a7a6be804",
                            "authorization": {"owner": "1", "access": "private"},
                            "@timestamp": "2021-05-01T24:00:00",
                        },
                    },
                    {
                        "_index": "riya-pbench.v6.run-toc.2021-05",
                        "_type": "_doc",
                        "_id": "3bba25b62fhdgfajgsfdty6797ed06a",
                        "_score": 0.0,
                        "_source": {
                            "parent": "/1-default",
                            "directory": "/1-default/sample1",
                            "mtime": "2021-05-01T24:00:00",
                            "mode": "0o755",
                            "name": "sample1",
                            "ancestor_path_elements": ["1-default"],
                            "files": [
                                {
                                    "name": "result.txt",
                                    "mtime": "2021-05-01T24:00:00",
                                    "size": 0,
                                    "mode": "0o644",
                                    "type": "reg",
                                },
                                {
                                    "name": "user-benchmark.cmd",
                                    "mtime": "2021-05-01T24:00:00",
                                    "size": 114,
                                    "mode": "0o755",
                                    "type": "reg",
                                },
                            ],
                            "run_data_parent": "ece030bdgfkjasdkf7435e6a7a6be804",
                            "authorization": {"owner": "1", "access": "private"},
                            "@timestamp": "2021-05-01T24:00:00",
                        },
                    },
                ],
            },
        }
        index = self.build_index_from_metadata()

        # get_expected_status() expects to read username and access from the
        # JSON client payload, however this API acquires that information
        # from the Dataset. Construct a fake payload corresponding to the
        # attach_dataset fixture.
        auth_json = {"user": "drb", "access": "private"}
        expected_status = self.get_expected_status(
            auth_json, build_auth_header["header_param"]
        )

        response = query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.payload,
            index,
            expected_status,
            json=response_payload,
            status=HTTPStatus.OK,
            headers=build_auth_header["header"],
        )
        if expected_status == HTTPStatus.OK:
            res_json = response.json
            expected_result = {
                "directories": ["sample1"],
                "files": [
                    {
                        "name": "reference-result",
                        "mtime": "2021-05-01T24:00:00",
                        "size": 0,
                        "mode": "0o777",
                        "type": "sym",
                        "linkpath": "sample1",
                    }
                ],
            }
            assert expected_result == res_json

    def test_subdirectory_query(
        self,
        server_config,
        query_api,
        pbench_token,
        build_auth_header,
        find_template,
        provide_metadata,
    ):
        """
        Check the construction of Elasticsearch query URI and filtering of the
        response body. Note that the mock set up by the attach_dataset fixture
        matches the dataset name to the dataset's owner.
        """
        response_payload = {
            "took": 7,
            "timed_out": False,
            "_shards": {"total": 3, "successful": 3, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "max_score": 0.0,
                "hits": [
                    {
                        "_index": "riya-pbench.v6.run-toc.2021-05",
                        "_type": "_doc",
                        "_id": "d4a8cc7c4ecef7vshg4tjhrew174828d",
                        "_score": 0.0,
                        "_source": {
                            "parent": "/",
                            "directory": "/1-default",
                            "mtime": "2021-05-01T24:00:00",
                            "mode": "0o755",
                            "name": "1-default",
                            "run_data_parent": "ece030bdgfkjasdkf7435e6a7a6be804",
                            "authorization": {"owner": "1", "access": "private"},
                            "@timestamp": "2021-05-01T24:00:00",
                        },
                    },
                    {
                        "_index": "riya-pbench.v6.run-toc.2021-05",
                        "_type": "_doc",
                        "_id": "3bba25b62fhdgfajgsfdty6797ed06a",
                        "_score": 0.0,
                        "_source": {
                            "parent": "/1-default",
                            "directory": "/1-default/sample1",
                            "mtime": "2021-05-01T24:00:00",
                            "mode": "0o755",
                            "name": "sample1",
                            "ancestor_path_elements": ["1-default"],
                            "files": [
                                {
                                    "name": "result.txt",
                                    "mtime": "2021-05-01T24:00:00",
                                    "size": 0,
                                    "mode": "0o644",
                                    "type": "reg",
                                },
                                {
                                    "name": "user-benchmark.cmd",
                                    "mtime": "2021-05-01T24:00:00",
                                    "size": 114,
                                    "mode": "0o755",
                                    "type": "reg",
                                },
                            ],
                            "run_data_parent": "ece030bdgfkjasdkf7435e6a7a6be804",
                            "authorization": {"owner": "1", "access": "private"},
                            "@timestamp": "2021-05-01T24:00:00",
                        },
                    },
                ],
            },
        }
        index = self.build_index_from_metadata()

        # get_expected_status() expects to read username and access from the
        # JSON client payload, however this API acquires that information
        # from the Dataset. Construct a fake payload corresponding to the
        # attach_dataset fixture.
        auth_json = {"user": "drb", "access": "private"}
        expected_status = self.get_expected_status(
            auth_json, build_auth_header["header_param"]
        )

        response = query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.payload,
            index,
            expected_status,
            json=response_payload,
            status=HTTPStatus.OK,
            headers=build_auth_header["header"],
        )
        if expected_status == HTTPStatus.OK:
            res_json = response.json
            expected_result = {"directories": ["sample1"], "files": []}
            assert expected_result == res_json

    def test_files_query(
        self,
        server_config,
        query_api,
        pbench_token,
        build_auth_header,
        find_template,
        provide_metadata,
    ):
        """
        Check the construction of Elasticsearch query URI and filtering of the
        response body. Note that the mock set up by the attach_dataset fixture
        matches the dataset name to the dataset's owner.
        """
        response_payload = {
            "took": 7,
            "timed_out": False,
            "_shards": {"total": 3, "successful": 3, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "max_score": 0.0,
                "hits": [
                    {
                        "_index": "riya-pbench.v6.run-toc.2021-05",
                        "_type": "_doc",
                        "_id": "9e95ccb385b7a7a2d70ededa07c391da",
                        "_score": 0.0,
                        "_source": {
                            "parent": "/",
                            "directory": "/1-default",
                            "mtime": "2021-05-01T24:00:00",
                            "mode": "0o755",
                            "files": [
                                {
                                    "name": "default.csv",
                                    "mtime": "2021-05-01T24:00:00",
                                    "size": 122,
                                    "mode": "0o644",
                                    "type": "reg",
                                }
                            ],
                            "run_data_parent": "ece030bdgfkjasdkf7435e6a7a6be804",
                            "authorization": {"owner": "1", "access": "private"},
                            "@timestamp": "2021-05-01T24:00:00",
                        },
                    }
                ],
            },
        }
        index = self.build_index_from_metadata()

        # get_expected_status() expects to read username and access from the
        # JSON client payload, however this API acquires that information
        # from the Dataset. Construct a fake payload corresponding to the
        # attach_dataset fixture.
        auth_json = {"user": "drb", "access": "private"}
        expected_status = self.get_expected_status(
            auth_json, build_auth_header["header_param"]
        )

        response = query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.payload,
            index,
            expected_status,
            json=response_payload,
            status=HTTPStatus.OK,
            headers=build_auth_header["header"],
        )
        if expected_status == HTTPStatus.OK:
            res_json = response.json
            expected_result = {
                "directories": [],
                "files": [
                    {
                        "name": "default.csv",
                        "mtime": "2021-05-01T24:00:00",
                        "size": 122,
                        "mode": "0o644",
                        "type": "reg",
                    }
                ],
            }
            assert expected_result == res_json

    def test_empty_query(
        self,
        server_config,
        query_api,
        pbench_token,
        build_auth_header,
        find_template,
        provide_metadata,
    ):
        """
        Check the construction of Elasticsearch query URI and filtering of the
        response body. Note that the mock set up by the attach_dataset fixture
        matches the dataset name to the dataset's owner.
        """
        response_payload = {
            "took": 55,
            "timed_out": False,
            "_shards": {"total": 3, "successful": 3, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 0, "relation": "eq"},
                "max_score": None,
                "hits": [],
            },
        }
        index = self.build_index_from_metadata()

        # get_expected_status() expects to read username and access from the
        # JSON client payload, however this API acquires that information
        # from the Dataset. Construct a fake payload corresponding to the
        # attach_dataset fixture.
        auth_json = {"user": "drb", "access": "private"}
        expected_status = self.get_expected_status(
            auth_json, build_auth_header["header_param"]
        )

        response = query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.payload,
            index,
            expected_status,
            json=response_payload,
            status=HTTPStatus.OK,
            headers=build_auth_header["header"],
        )
        if expected_status == HTTPStatus.OK:
            res_json = response.json
            expected_result = {"directories": [], "files": []}
            assert expected_result == res_json

    def test_get_index(self, attach_dataset, provide_metadata):
        drb = Dataset.query(name="drb")
        indices = self.cls_obj.get_index(drb, self.index_from_metadata)
        assert indices == "unit-test.v6.run-toc.2020-05"
