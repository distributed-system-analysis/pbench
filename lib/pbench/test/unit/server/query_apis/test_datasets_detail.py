import pytest
import requests
from http import HTTPStatus


class TestDatasetsDetail:
    """
    Unit testing for resources/DatasetsDetail class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    def build_index(self, server_config, dates):
        """
        Build the index list for query

        Args:
            dates (iterable): list of date strings
        """
        idx = server_config.get("Indexing", "index_prefix") + ".v6.run-data."
        index = "/"
        for d in dates:
            index += f"{idx}{d},"
        return index

    def test_non_accessible_user_data(self, client, server_config, pbench_token):
        """
        Test behavior when Authorization header does not have access to other user's data
        """
        # The pbench_token fixture logs in as user "drb"
        # Trying to access the data belong to the user "pp"
        response = client.post(
            f"{server_config.rest_uri}/datasets/detail",
            headers={"Authorization": "Bearer " + pbench_token},
            json={
                "user": "pp",
                "name": "dataset_name",
                "start": "2020-08",
                "end": "2020-10",
            },
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    @pytest.mark.parametrize(
        "user", ("drb", "pp"),
    )
    def test_accessing_data_with_invalid_token(
        self, client, server_config, pbench_token, user
    ):
        """
        Test behavior when Authorization header does not have access to other user's data
        """
        # valid token logout
        response = client.post(
            f"{server_config.rest_uri}/logout",
            headers=dict(Authorization="Bearer " + pbench_token),
        )
        assert response.status_code == HTTPStatus.OK
        response = client.post(
            f"{server_config.rest_uri}/datasets/detail",
            headers={"Authorization": "Bearer " + pbench_token},
            json={"user": user, "name": "bar", "start": "2020-08", "end": "2020-10"},
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_missing_json_object(self, client, server_config, pbench_token):
        """
        Test behavior when no JSON payload is given
        """
        response = client.post(
            f"{server_config.rest_uri}/datasets/detail",
            headers={"Authorization": "Bearer " + pbench_token},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == "Invalid request payload"

    @pytest.mark.parametrize(
        "keys",
        (
            {"user": "x"},
            {"name": "y"},
            {"start": "2020"},
            {"end": "2020"},
            {"user": "x", "start": "2020"},
            {"user": "x", "end": "2020"},
            {"user": "x", "name": "y", "start": "2021"},
            {"some_additional_key": "test"},
        ),
    )
    def test_missing_keys(self, client, server_config, keys, user_ok, pbench_token):
        """
        Test behavior when JSON payload does not contain
        all required keys.

        Note that "name", "start", and "end" are required whereas "user" is not mandatory;
        however, Pbench will silently ignore any additional keys that are
        specified.
        """
        response = client.post(
            f"{server_config.rest_uri}/datasets/detail",
            headers={"Authorization": "Bearer " + pbench_token},
            json=keys,
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        missing = [k for k in ("name", "start", "end") if k not in keys]
        assert (
            response.json.get("message")
            == f"Missing required parameters: {','.join(missing)}"
        )

    def test_bad_dates(self, client, server_config, user_ok, pbench_token):
        """
        Test behavior when a bad date string is given
        """
        response = client.post(
            f"{server_config.rest_uri}/datasets/detail",
            headers={"Authorization": "Bearer " + pbench_token},
            json={
                "user": "drb",
                "name": "footest",
                "start": "2020-12",
                "end": "2020-19",
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert (
            response.json.get("message")
            == "Value '2020-19' (str) cannot be parsed as a date/time string"
        )

    @pytest.mark.parametrize(
        "user", ("drb", "badwolf", "no_user"),
    )
    def test_query(
        self,
        client,
        server_config,
        query_api,
        user_ok,
        find_template,
        build_auth_header,
        user,
    ):
        """
        Check the construction of Elasticsearch query URI and filtering of the response body.
        The test will run once with each parameter supplied from the local parameterization,
        and, for each of those, three times with different values of the build_auth_header fixture.
        """
        json = {
            "user": user,
            "name": "fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13",
            "start": "2020-08",
            "end": "2020-10",
        }
        if user == "no_user":
            json.pop("user", None)

        response_payload = {
            "took": 112,
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
                            "@timestamp": "2020-04-29T12:49:13.560620",
                            "@metadata": {
                                "file-date": "2020-11-20T21:01:54.532281",
                                "file-name": "/pbench/archive/fs-version-001/dhcp31-187.example.com/fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13.tar.xz",
                                "file-size": 216319392,
                                "md5": "12fb1e952fd826727810868c9327254f",
                                "toc-prefix": "fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13",
                                "pbench-agent-version": "0.68-1gf4c94b4d",
                                "controller_dir": "dhcp31-187.example.com",
                                "tar-ball-creation-timestamp": "2020-04-29T15:16:51.880540",
                                "raw_size": 292124533,
                            },
                            "@generated-by": "3319a130c156f978fa6dc809012b5ba0",
                            "authorization": {"user": "unknown", "access": "private"},
                            "run": {
                                "controller": "dhcp31-187.example.com",
                                "name": "fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13",
                                "script": "fio",
                                "config": "rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus",
                                "date": "2020-04-29T12:48:33",
                                "iterations": "0__bs=4k_iodepth=1_iodepth_batch_complete_max=1, 1__bs=32k_iodepth=1_iodepth_batch_complete_max=1, 2__bs=256k_iodepth=1_iodepth_batch_complete_max=1, 3__bs=4k_iodepth=8_iodepth_batch_complete_max=8, 4__bs=32k_iodepth=8_iodepth_batch_complete_max=8, 5__bs=256k_iodepth=8_iodepth_batch_complete_max=8, 6__bs=4k_iodepth=16_iodepth_batch_complete_max=16, 7__bs=32k_iodepth=16_iodepth_batch_complete_max=16, 8__bs=256k_iodepth=16_iodepth_batch_complete_max=16",
                                "toolsgroup": "default",
                                "start": "2020-04-29T12:49:13.560620",
                                "end": "2020-04-29T13:30:04.918704",
                                "id": "12fb1e952fd826727810868c9327254f",
                            },
                            "host_tools_info": [
                                {
                                    "hostname": "dhcp31-187",
                                    "tools": {
                                        "iostat": "--interval=3",
                                        "mpstat": "--interval=3",
                                        "perf": "--record-opts='record -a --freq=100'",
                                        "pidstat": "--interval=30",
                                        "proc-interrupts": "--interval=3",
                                        "proc-vmstat": "--interval=3",
                                        "sar": "--interval=3",
                                        "turbostat": "--interval=3",
                                    },
                                }
                            ],
                        },
                        "sort": ["drb.v6.run-data.2020-04"],
                    }
                ],
            },
        }

        index = self.build_index(server_config, ("2020-08", "2020-09", "2020-10"))

        expected_status = HTTPStatus.OK

        # Determine whether we should expect the request to succeed, or to
        # fail with a permission error. We always authenticate with the
        # user "drb" as fabricated by the build_auth_header fixure; we
        # don't expect success for an "invalid" authentication, for a different
        # user, or for an invalid username.
        if (
            not user
            or user == "no_user"
            or build_auth_header["header_param"] == "valid"
        ) and user != "badwolf":
            expected_status = HTTPStatus.OK
        else:
            expected_status = HTTPStatus.FORBIDDEN

        response = query_api(
            "/datasets/detail",
            "/_search?ignore_unavailable=true",
            json,
            index,
            expected_status,
            headers=build_auth_header["header"],
            json=response_payload,
        )
        assert response.status_code == expected_status
        if response.status_code == HTTPStatus.OK:
            res_json = response.json

            expected = {
                "hostTools": [
                    {
                        "hostname": "dhcp31-187",
                        "tools": {
                            "iostat": "--interval=3",
                            "mpstat": "--interval=3",
                            "perf": "--record-opts='record -a --freq=100'",
                            "pidstat": "--interval=30",
                            "proc-interrupts": "--interval=3",
                            "proc-vmstat": "--interval=3",
                            "sar": "--interval=3",
                            "turbostat": "--interval=3",
                        },
                    }
                ],
                "runMetadata": {
                    "config": "rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus",
                    "controller": "dhcp31-187.example.com",
                    "controller_dir": "dhcp31-187.example.com",
                    "date": "2020-04-29T12:48:33",
                    "end": "2020-04-29T13:30:04.918704",
                    "file-date": "2020-11-20T21:01:54.532281",
                    "file-name": "/pbench/archive/fs-version-001/dhcp31-187.example.com/fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13.tar.xz",
                    "file-size": 216319392,
                    "id": "12fb1e952fd826727810868c9327254f",
                    "iterations": "0__bs=4k_iodepth=1_iodepth_batch_complete_max=1, 1__bs=32k_iodepth=1_iodepth_batch_complete_max=1, 2__bs=256k_iodepth=1_iodepth_batch_complete_max=1, 3__bs=4k_iodepth=8_iodepth_batch_complete_max=8, 4__bs=32k_iodepth=8_iodepth_batch_complete_max=8, 5__bs=256k_iodepth=8_iodepth_batch_complete_max=8, 6__bs=4k_iodepth=16_iodepth_batch_complete_max=16, 7__bs=32k_iodepth=16_iodepth_batch_complete_max=16, 8__bs=256k_iodepth=16_iodepth_batch_complete_max=16",
                    "md5": "12fb1e952fd826727810868c9327254f",
                    "name": "fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13",
                    "pbench-agent-version": "0.68-1gf4c94b4d",
                    "raw_size": 292124533,
                    "script": "fio",
                    "start": "2020-04-29T12:49:13.560620",
                    "tar-ball-creation-timestamp": "2020-04-29T15:16:51.880540",
                    "toc-prefix": "fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13",
                    "toolsgroup": "default",
                },
            }
            assert expected == res_json

    def test_empty_query(
        self,
        client,
        server_config,
        query_api,
        user_ok,
        find_template,
        build_auth_header,
    ):
        """
        Check the handling of a query that doesn't return any data.
        The test will run thrice with different values of the build_auth_header
        fixture.
        """
        json = {
            "user": "drb",
            "name": "fio",
            "start": "2020-08",
            "end": "2020-10",
        }
        response_payload = {
            "hits": {
                "total": {"value": 0, "relation": "eq"},
                "max_score": None,
                "hits": [],
            },
        }
        expected_status = HTTPStatus.BAD_REQUEST
        if build_auth_header["header_param"] != "valid":
            expected_status = HTTPStatus.FORBIDDEN

        index = self.build_index(server_config, ("2020-08", "2020-09", "2020-10"))
        response = query_api(
            "/datasets/detail",
            "/_search?ignore_unavailable=true",
            json,
            index,
            expected_status,
            headers=build_auth_header["header"],
            json=response_payload,
        )
        assert response.status_code == expected_status
        if response.status_code == HTTPStatus.BAD_REQUEST:
            assert response.json["message"].find("dataset has gone missing") != -1

    def test_nonunique_query(
        self, client, server_config, query_api, user_ok, find_template
    ):
        """
        Check the handling of a query that returns too much data.
        """
        json = {
            "name": "fio",
            "start": "2020-08",
            "end": "2020-10",
        }
        response_payload = {
            "hits": {
                "total": {"value": 0, "relation": "eq"},
                "max_score": None,
                "hits": [{"a": True}, {"b": False}],
            },
        }

        index = self.build_index(server_config, ("2020-08", "2020-09", "2020-10"))
        response = query_api(
            "/datasets/detail",
            "/_search?ignore_unavailable=true",
            json,
            index,
            HTTPStatus.BAD_REQUEST,
            json=response_payload,
        )
        assert response.json["message"].find("Too many hits for a unique query") != -1

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
        self, client, server_config, query_api, exceptions, user_ok, find_template
    ):
        """
        Check that an exception in calling Elasticsearch is reported correctly.
        """
        json = {
            "name": "foobar",
            "start": "2020-08",
            "end": "2020-08",
        }
        index = self.build_index(server_config, ("2020-08",))
        query_api(
            "/datasets/detail",
            "/_search?ignore_unavailable=true",
            json,
            index,
            exceptions["status"],
            body=exceptions["exception"],
        )

    @pytest.mark.parametrize("errors", (400, 500, 409))
    def test_http_error(self, server_config, query_api, errors, user_ok, find_template):
        """
        Check that an Elasticsearch error is reported correctly through the
        response.raise_for_status() and Pbench handlers.
        """
        json = {
            "name": "foobar",
            "start": "2020-08",
            "end": "2020-08",
        }
        index = self.build_index(server_config, ("2020-08",))
        query_api(
            "/datasets/detail",
            "/_search?ignore_unavailable=true",
            json,
            index,
            HTTPStatus.BAD_GATEWAY,
            status=errors,
        )
