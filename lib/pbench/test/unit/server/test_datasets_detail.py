import pytest
import re
import requests

from pbench.server.api.resources.query_apis import get_es_url, get_index_prefix


@pytest.fixture
def query_helper(client, server_config, requests_mock):
    """
    query_helper Help controller queries that want to interact with a mocked
    Elasticsearch service.

    This is a fixture which exposes a function of the same name that can be
    used to set up and validate a mocked Elasticsearch query with a JSON
    payload and an expected status.

    Parameters to the mocked Elasticsearch POST are passed as keyword
    parameters: these can be any of the parameters supported by the
    request_mock post method. The most common are 'json' for the JSON
    response payload, and 'exc' to throw an exception.

    :return: the response object for further checking
    """

    def query_helper(payload, expected_index, expected_status, server_config, **kwargs):
        es_url = get_es_url(server_config)
        requests_mock.post(re.compile(f"{es_url}"), **kwargs)
        response = client.post(
            f"{server_config.rest_uri}/datasets/detail", json=payload
        )
        assert requests_mock.last_request.url == (
            es_url + expected_index + "/_search?ignore_unavailable=true"
        )
        assert response.status_code == expected_status
        return response

    return query_helper


class TestDatasetsDetail:
    """
    Unit testing for resources/DatasetsDetail class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    def build_index(self, server_config, dates):
        """
        build_index Build the index list for query

        Args:
            dates (iterable): list of date strings
        """
        prefix = get_index_prefix(server_config)
        idx = prefix + ".v6.run-data."
        index = "/"
        for d in dates:
            index += f"{idx}{d},"
        return index

    def test_missing_json_object(self, client, server_config):
        """
        test_missing_json_object Test behavior when no JSON payload is given
        """
        response = client.post(f"{server_config.rest_uri}/datasets/detail")
        assert response.status_code == 400
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
            {"start": "2020", "end": "2020"},
        ),
    )
    def test_missing_keys(self, client, server_config, keys):
        """
        test_missing_keys Test behavior when JSON payload does not contain
        all required keys.

        Note that "user", "name", "start", and "end" are all required;
        however, Pbench will silently ignore any additional keys that are
        specified.
       """
        response = client.post(f"{server_config.rest_uri}/datasets/detail", json=keys)
        assert response.status_code == 400
        missing = [k for k in ("user", "name", "start", "end") if k not in keys]
        assert (
            response.json.get("message") == f"Missing request data: {','.join(missing)}"
        )

    def test_bad_dates(self, client, server_config):
        """
        test_bad_dates Test behavior when a bad date string is given
        """
        response = client.post(
            f"{server_config.rest_uri}/datasets/detail",
            json={
                "user": "drb",
                "name": "footest",
                "start": "2020-15",
                "end": "2020-19",
            },
        )
        assert response.status_code == 400
        assert response.json.get("message") == "Invalid start or end time string"

    def test_query(self, client, server_config, query_helper):
        """
        test_query Check the construction of Elasticsearch query URI
        and filtering of the response body.
        """
        json = {
            "user": "drb",
            "name": "fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13",
            "start": "2020-08",
            "end": "2020-10",
        }
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
                                "file-name": "/pbench/archive/fs-version-001/dhcp31-187.perf.lab.eng.bos.redhat.com/fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13.tar.xz",
                                "file-size": 216319392,
                                "md5": "12fb1e952fd826727810868c9327254f",
                                "toc-prefix": "fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13",
                                "pbench-agent-version": "0.68-1gf4c94b4d",
                                "controller_dir": "dhcp31-187.perf.lab.eng.bos.redhat.com",
                                "tar-ball-creation-timestamp": "2020-04-29T15:16:51.880540",
                                "raw_size": 292124533,
                            },
                            "@generated-by": "3319a130c156f978fa6dc809012b5ba0",
                            "authorization": {"user": "unknown", "access": "private"},
                            "run": {
                                "controller": "dhcp31-187.perf.lab.eng.bos.redhat.com",
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
        response = query_helper(json, index, 200, server_config, json=response_payload)
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
                "controller": "dhcp31-187.perf.lab.eng.bos.redhat.com",
                "controller_dir": "dhcp31-187.perf.lab.eng.bos.redhat.com",
                "date": "2020-04-29T12:48:33",
                "end": "2020-04-29T13:30:04.918704",
                "file-date": "2020-11-20T21:01:54.532281",
                "file-name": "/pbench/archive/fs-version-001/dhcp31-187.perf.lab.eng.bos.redhat.com/fio_rhel8_kvm_perf43_preallocfull_nvme_run4_iothread_isolcpus_2020.04.29T12.49.13.tar.xz",
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

    @pytest.mark.parametrize(
        "exceptions",
        (
            {"exception": requests.exceptions.HTTPError, "status": 502},
            {"exception": requests.exceptions.ConnectionError, "status": 502},
            {"exception": requests.exceptions.Timeout, "status": 504},
            {"exception": requests.exceptions.InvalidURL, "status": 500},
            {"exception": Exception, "status": 500},
        ),
    )
    def test_http_error(self, client, server_config, query_helper, exceptions):
        """
        test_http_error Check that an Elasticsearch error is reported
        correctly.
       """
        json = {
            "user": "drb",
            "name": "foobar",
            "start": "2020-08",
            "end": "2020-08",
        }
        index = self.build_index(server_config, ("2020-08",))
        query_helper(
            json,
            index,
            exceptions["status"],
            server_config,
            exc=exceptions["exception"],
        )
