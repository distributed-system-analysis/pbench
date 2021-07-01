import pytest
import requests
from http import HTTPStatus


class TestDatasetsList:
    """
    Unit testing for resources/DatasetsList class.

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
            f"{server_config.rest_uri}/datasets/list",
            headers={"Authorization": "Bearer " + pbench_token},
            json={
                "user": "pp",
                "controller": "cpntroller.name",
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
        assert response.status_code == 200
        response = client.post(
            f"{server_config.rest_uri}/datasets/list",
            headers={"Authorization": "Bearer " + pbench_token},
            json={"user": user, "start": "2020-08", "end": "2020-10"},
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_missing_json_object(self, client, server_config, pbench_token):
        """
        Test behavior when no JSON payload is given
        """
        response = client.post(
            f"{server_config.rest_uri}/datasets/list",
            headers={"Authorization": "Bearer " + pbench_token},
        )
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
            {"some_additional_key": "test"},
        ),
    )
    def test_missing_keys(self, client, server_config, pbench_token, keys):
        """
        Test behavior when JSON payload does not contain
        all required keys.

        Note that "start", "controller", "end" are required whereas "user" is not mandatory;
        however, Pbench will silently ignore any additional keys that are
        specified.
       """
        response = client.post(
            f"{server_config.rest_uri}/datasets/list",
            headers={"Authorization": "Bearer " + pbench_token},
            json=keys,
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        missing = [k for k in ("controller", "start", "end") if k not in keys]
        assert (
            response.json.get("message")
            == f"Missing required parameters: {','.join(missing)}"
        )

    def test_bad_dates(self, client, server_config, pbench_token):
        """
        Test behavior when a bad date string is given
        """
        response = client.post(
            f"{server_config.rest_uri}/datasets/list",
            headers={"Authorization": "Bearer " + pbench_token},
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
    @pytest.mark.parametrize(
        "user", ("drb", "", "no_user", None),
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
            "controller": "dbutenho.csb",
            "start": "2020-08",
            "end": "2020-10",
        }
        if user == "no_user":
            json.pop("user", None)
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

        # If we're not asking about a particular user, or if the user
        # field is to be omitted altogether, or if we have a valid
        # token, then the request should succeed.
        if (
            not user
            or user == "no_user"
            or build_auth_header["header_param"] == "valid"
        ):
            expected_status = HTTPStatus.OK
        else:
            expected_status = HTTPStatus.FORBIDDEN

        response = query_api(
            "/datasets/list",
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
            "user": "",
            "controller": "foobar",
            "start": "2020-08",
            "end": "2020-08",
        }
        index = self.build_index(server_config, ("2020-08",))
        query_api(
            "/datasets/list",
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
            "user": "",
            "controller": "foobar",
            "start": "2020-08",
            "end": "2020-08",
        }
        index = self.build_index(server_config, ("2020-08",))
        query_api(
            "/datasets/list",
            "/_search?ignore_unavailable=true",
            json,
            index,
            HTTPStatus.BAD_GATEWAY,
            status=errors,
        )
