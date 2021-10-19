import pytest
from http import HTTPStatus
from pbench.server.api.resources.query_apis.datasets_list import DatasetsList
from pbench.test.unit.server.query_apis.commons import Commons


class TestDatasetsList(Commons):
    """
    Unit testing for resources/DatasetsList class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        super()._setup(
            cls_obj=DatasetsList(client.config, client.logger),
            pbench_endpoint="/datasets/list",
            elastic_endpoint="/_search?ignore_unavailable=true",
            payload={
                "user": "drb",
                "access": "private",
                "controller": "cpntroller.name",
                "start": "2020-08",
                "end": "2020-10",
            },
        )

    @pytest.mark.parametrize(
        "query_api",
        [{"pbench": "/datasets/list", "elastic": "/_search?ignore_unavailable=true"}],
        indirect=True,
    )
    @pytest.mark.parametrize("user", ("drb", "badwolf", "no_user"))
    def test_query(
        self, client, server_config, query_api, find_template, build_auth_header, user,
    ):
        """
        Check the construction of Elasticsearch query URI and filtering of the response body.
        The test will run once with each parameter supplied from the local parameterization,
        and, for each of those, three times with different values of the build_auth_header fixture.
        """
        payload = {
            "user": user,
            "access": "private",
            "controller": "dbutenho.csb",
            "start": "2020-08",
            "end": "2020-10",
        }
        if user == "no_user":
            del payload["user"]
            payload["access"] = "public"
        response_payload = {
            "took": 6,
            "timed_out": False,
            "_shards": {"total": 5, "successful": 5, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "max_score": None,
                "hits": [
                    {
                        "_index": "drb.v6.run-data.2020-04",
                        "_type": "_doc",
                        "_id": "12fb1e952fd826727810868c9327254f",
                        "_score": None,
                        "_source": {
                            "authorization": {"access": "private", "user": "unknown"},
                            "@metadata": {"controller_dir": "dhcp31-187.example.com"},
                            "run": {
                                "controller": "dhcp31-187.example.com",
                                "name": "fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13",
                                "start": "2020-04-29T12:49:13.560620",
                                "end": "2020-04-29T13:30:04.918704",
                                "id": "12fb1e952fd826727810868c9327254f",
                                "config": "rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus",
                            },
                        },
                        "sort": [1588167004918],
                    }
                ],
            },
        }

        index = self.build_index(
            server_config, self.date_range(self.payload["start"], self.payload["end"])
        )

        expected_status = self.get_expected_status(
            payload, build_auth_header["header_param"]
        )
        response = query_api(
            "/datasets/list",
            "/_search?ignore_unavailable=true",
            payload,
            index,
            expected_status,
            headers=build_auth_header["header"],
            json=response_payload,
        )
        assert response.status_code == expected_status
        if response.status_code == HTTPStatus.OK:
            res_json = response.json
            assert isinstance(res_json, dict)
            assert len(res_json.keys()) == 1
            data = res_json["dhcp31-187.example.com"]
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["@metadata.controller_dir"] == "dhcp31-187.example.com"
            assert (
                data[0]["config"]
                == "rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus"
            )
            assert data[0]["controller"] == "dhcp31-187.example.com"
            assert (
                data[0]["result"]
                == "fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13"
            )
            assert data[0]["start"] == "2020-04-29T12:49:13.560620"
            assert data[0]["end"] == "2020-04-29T13:30:04.918704"
            assert data[0]["id"] == "12fb1e952fd826727810868c9327254f"

    def test_metadata(
        self,
        client,
        server_config,
        query_api,
        find_template,
        provide_metadata,
        pbench_token,
    ):
        """
        This is nearly a repeat of the basic `test_query`; while that focuses
        on validating the transformation of Elasticsearch data, this tries to
        focus on the PostgreSQL dataset metadata... but necessarily has to
        borrow much of the setup.
        """
        payload = {
            "user": "drb",
            "controller": "node",
            "start": "2020-08",
            "end": "2020-10",
            "metadata": ["dashboard.seen", "server.deletion", "user.contact"],
        }
        response_payload = {
            "took": 6,
            "timed_out": False,
            "_shards": {"total": 5, "successful": 5, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "max_score": None,
                "hits": [
                    {
                        "_index": "drb.v6.run-data.2020-04",
                        "_type": "_doc",
                        "_id": "12fb1e952fd826727810868c9327254f",
                        "_score": None,
                        "_source": {
                            "authorization": {"access": "private", "user": "unknown"},
                            "@metadata": {"controller_dir": "dhcp31-187.example.com"},
                            "run": {
                                "controller": "node",
                                "name": "drb",
                                "start": "2020-04-29T12:49:13.560620",
                                "end": "2020-04-29T13:30:04.918704",
                                "id": "12fb1e952fd826727810868c9327254f",
                                "config": "rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus",
                            },
                        },
                        "sort": [1588167004918],
                    },
                    {
                        "_index": "drb.v6.run-data.2020-04",
                        "_type": "_doc",
                        "_id": "12fb1e952fd826727810868c9327254f",
                        "_score": None,
                        "_source": {
                            "authorization": {"access": "private", "user": "unknown"},
                            "@metadata": {"controller_dir": "dhcp31-187.example.com"},
                            "run": {
                                "controller": "node",
                                "name": "test",
                                "start": "2020-04-29T12:49:13.560620",
                                "end": "2020-04-29T13:30:04.918704",
                                "id": "12fb1e952fd826727810868c9327254f",
                                "config": "rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus",
                            },
                        },
                        "sort": [1588167004918],
                    },
                ],
            },
        }

        index = self.build_index(
            server_config, self.date_range(self.payload["start"], self.payload["end"])
        )

        response = query_api(
            "/datasets/list",
            "/_search?ignore_unavailable=true",
            payload,
            index,
            HTTPStatus.OK,
            headers={"authorization": f"Bearer {pbench_token}"},
            json=response_payload,
        )
        assert response.status_code == HTTPStatus.OK
        res_json = response.json
        assert isinstance(res_json, dict)
        assert len(res_json) == 1
        data = res_json["node"]
        assert isinstance(data, list)
        assert len(data) == 2
        assert data == [
            {
                "@metadata.controller_dir": "dhcp31-187.example.com",
                "config": "rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus",
                "controller": "node",
                "result": "drb",
                "start": "2020-04-29T12:49:13.560620",
                "end": "2020-04-29T13:30:04.918704",
                "id": "12fb1e952fd826727810868c9327254f",
                "serverMetadata": {
                    "dashboard.seen": None,
                    "server.deletion": "2022-12-25",
                    "user.contact": "me@example.com",
                },
            },
            {
                "@metadata.controller_dir": "dhcp31-187.example.com",
                "config": "rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus",
                "controller": "node",
                "result": "test",
                "start": "2020-04-29T12:49:13.560620",
                "end": "2020-04-29T13:30:04.918704",
                "id": "12fb1e952fd826727810868c9327254f",
                "serverMetadata": {
                    "dashboard.seen": None,
                    "server.deletion": "2023-01-25",
                    "user.contact": "you@example.com",
                },
            },
        ]
