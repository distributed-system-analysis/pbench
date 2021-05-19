import pytest
import requests
from http import HTTPStatus
from pbench.test.unit.server.query_apis.conftest import make_http_exception


class TestDatasetsList:
    """
    Unit testing for resources/DatasetsList class.

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
        idx = server_config.get("Indexing", "index_prefix") + ".v6.run-data."
        index = "/"
        for d in dates:
            index += f"{idx}{d},"
        return index

    def test_missing_json_object(self, client, server_config):
        """
        test_missing_json_object Test behavior when no JSON payload is given
        """
        response = client.post(f"{server_config.rest_uri}/datasets/list")
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == "Invalid request payload"

    @pytest.mark.parametrize(
        "keys",
        (
            {"user": "x"},
            {"controller": "y"},
            {"start": "2020"},
            {"end": "2020"},
            {"user": "x", "start": "2020"},
            {"user": "x", "end": "2020"},
            {"user": "x", "controller": "y", "start": "2021"},
            {"start": "2020", "end": "2020"},
        ),
    )
    def test_missing_keys(self, client, server_config, keys):
        """
        test_missing_keys Test behavior when JSON payload does not contain
        all required keys.

        Note that "user", "controller", "start", and "end" are all required;
        however, Pbench will silently ignore any additional keys that are
        specified.
       """
        response = client.post(f"{server_config.rest_uri}/datasets/list", json=keys)
        assert response.status_code == HTTPStatus.BAD_REQUEST
        missing = [k for k in ("user", "controller", "start", "end") if k not in keys]
        assert (
            response.json.get("message")
            == f"Missing required parameters: {','.join(missing)}"
        )

    def test_bad_dates(self, client, server_config):
        """
        test_bad_dates Test behavior when a bad date string is given
        """
        response = client.post(
            f"{server_config.rest_uri}/datasets/list",
            json={
                "user": "drb",
                "controller": "dbutenho.csb",
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
        "query_api",
        [{"pbench": "/datasets/list", "elastic": "/_search?ignore_unavailable=true"}],
        indirect=True,
    )
    def test_query(self, client, server_config, query_api, user_ok, find_template):
        """
        test_query Check the construction of Elasticsearch query URI
        and filtering of the response body.
        """
        json = {
            "user": "drb",
            "controller": "dbutenho.csb",
            "start": "2020-08",
            "end": "2020-10",
        }
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

        index = self.build_index(server_config, ("2020-08", "2020-09", "2020-10"))
        response = query_api(
            json, index, HTTPStatus.OK, server_config, json=response_payload
        )
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

    @pytest.mark.parametrize(
        "exceptions",
        (
            {
                "exception": make_http_exception(HTTPStatus.BAD_REQUEST),
                "status": HTTPStatus.BAD_GATEWAY,
            },
            {
                "exception": requests.exceptions.ConnectionError,
                "status": HTTPStatus.BAD_GATEWAY,
            },
            {
                "exception": requests.exceptions.Timeout,
                "status": HTTPStatus.GATEWAY_TIMEOUT,
            },
            {
                "exception": requests.exceptions.InvalidURL,
                "status": HTTPStatus.INTERNAL_SERVER_ERROR,
            },
            {"exception": Exception, "status": HTTPStatus.INTERNAL_SERVER_ERROR},
        ),
    )
    @pytest.mark.parametrize(
        "query_api",
        [{"pbench": "/datasets/list", "elastic": "/_search?ignore_unavailable=true"}],
        indirect=True,
    )
    def test_http_error(
        self, client, server_config, query_api, exceptions, user_ok, find_template
    ):
        """
        test_http_error Check that an Elasticsearch error is reported
        correctly.
       """
        json = {
            "user": "drb",
            "controller": "foobar",
            "start": "2020-08",
            "end": "2020-08",
        }
        index = self.build_index(server_config, ("2020-08",))
        query_api(
            json,
            index,
            exceptions["status"],
            server_config,
            exc=exceptions["exception"],
        )
