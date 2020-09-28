import os
import socket

import pytest
import re
import requests

from pathlib import Path
from werkzeug.utils import secure_filename


class TestHostInfo:
    @staticmethod
    def test_host_info(client, pytestconfig, caplog):
        tmp_d = pytestconfig.cache.get("TMP", None)
        expected_message = (
            f"pbench@pbench.example.com:{tmp_d}/srv/pbench"
            "/pbench-move-results-receive"
            "/fs-version-002"
        )
        response = client.get(f"{client.config['REST_URI']}/host_info")

        assert response.status_code == 200
        assert response.json.get("message") == expected_message
        for record in caplog.records:
            assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")


class TestElasticsearch:
    @staticmethod
    def test_json_object(client, caplog):
        response = client.post(f"{client.config['REST_URI']}/elasticsearch")
        assert response.status_code == 400
        assert (
            response.json.get("message")
            == "Elasticsearch: Invalid json object in request"
        )
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"

    @staticmethod
    def test_empty_url_path(client, caplog):
        response = client.post(
            f"{client.config['REST_URI']}/elasticsearch", json={"indices": ""}
        )
        assert response.status_code == 400
        assert (
            response.json.get("message")
            == "Missing indices path in the Elasticsearch request"
        )
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"

    @staticmethod
    def test_bad_request(client, caplog, requests_mock):
        requests_mock.post(
            "http://elasticsearch.example.com:7080/some_invalid_url", status_code=400
        )
        response = client.post(
            f"{client.config['REST_URI']}/elasticsearch",
            json={"indices": "some_invalid_url", "payload": '{ "babble": "42" }'},
        )
        assert response.status_code == 400

        # This is a bit awkward, but the requests_mock throws in its own
        # DEBUG log record to announce the POST; so allow it. (But don't
        # fail if it's missing.)
        if len(caplog.records) > 0:
            assert len(caplog.records) == 2
            assert caplog.records[0].levelname == "DEBUG"
            assert caplog.records[0].name == "requests_mock.adapter"


class TestGraphQL:
    @staticmethod
    def test_json_object(client, caplog):
        response = client.post(f"{client.config['REST_URI']}/graphql")
        assert response.status_code == 400
        assert response.json.get("message") == "GraphQL: Invalid json object in request"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"


class TestUpload:
    @staticmethod
    def test_missing_filename_header_upload(client, caplog):
        expected_message = (
            "Missing filename header, "
            "POST operation requires a filename header to name the uploaded file"
        )
        response = client.put(
            f"{client.config['REST_URI']}/upload/ctrl/{socket.gethostname()}"
        )
        assert response.status_code == 400
        assert response.json.get("message") == expected_message
        for record in caplog.records:
            assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")

    @staticmethod
    def test_missing_md5sum_header_upload(client, caplog):
        expected_message = "Missing md5sum header, POST operation requires md5sum of an uploaded file in header"
        response = client.put(
            f"{client.config['REST_URI']}/upload/ctrl/{socket.gethostname()}",
            headers={"filename": "f.tar.xz"},
        )
        assert response.status_code == 400
        assert response.json.get("message") == expected_message
        for record in caplog.records:
            assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")

    @staticmethod
    @pytest.mark.parametrize("bad_extension", ("test.tar.bad", "test.tar", "test.tar."))
    def test_bad_extension_upload(client, bad_extension, caplog):
        expected_message = "File extension not supported. Only .xz"
        response = client.put(
            f"{client.config['REST_URI']}/upload/ctrl/{socket.gethostname()}",
            headers={"filename": bad_extension, "Content-MD5": "md5sum"},
        )
        assert response.status_code == 400
        assert response.json.get("message") == expected_message
        for record in caplog.records:
            assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")

    @staticmethod
    def test_empty_upload(client, pytestconfig, caplog):
        expected_message = "Upload failed, Content-Length received in header is 0"
        filename = "tmp.tar.xz"
        tmp_d = pytestconfig.cache.get("TMP", None)
        Path(tmp_d, filename).touch()

        with open(Path(tmp_d, filename), "rb") as data_fp:
            response = client.put(
                f"{client.config['REST_URI']}/upload/ctrl/{socket.gethostname()}",
                data=data_fp,
                headers={
                    "filename": "log.tar.xz",
                    "Content-MD5": "d41d8cd98f00b204e9800998ecf8427e",
                },
            )
        assert response.status_code == 400
        assert response.json.get("message") == expected_message
        for record in caplog.records:
            assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")

    @staticmethod
    def test_upload(client, pytestconfig, caplog):
        filename = "log.tar.xz"
        datafile = Path("./lib/pbench/test/unit/server/fixtures/upload/", filename)

        with open(f"{datafile}.md5") as md5sum_check:
            md5sum = md5sum_check.read()

        with open(datafile, "rb") as data_fp:
            response = client.put(
                f"{client.config['REST_URI']}/upload/ctrl/{socket.gethostname()}",
                data=data_fp,
                headers={"filename": filename, "Content-MD5": md5sum},
            )

        assert response.status_code == 201, repr(response)
        sfilename = secure_filename(filename)
        tmp_d = pytestconfig.cache.get("TMP", None)
        receive_dir = os.path.join(
            tmp_d, "srv", "pbench", "pbench-move-results-receive", "fs-version-002"
        )
        assert os.path.exists(receive_dir), (
            f"receive_dir = '{receive_dir}', filename = '{filename}',"
            f" sfilename = '{sfilename}'"
        )
        for record in caplog.records:
            assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")


@pytest.fixture
def query_helper(client, requests_mock):
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

    def query_helper(payload, expected_index, expected_status, **kwargs):
        requests_mock.post(re.compile(f'{client.config["ES_URL"]}'), **kwargs)
        response = client.post(
            f"{client.config['REST_URI']}/controllers/list", json=payload
        )
        assert requests_mock.last_request.url == (
            client.config["ES_URL"]
            + expected_index
            + "/_search?ignore_unavailable=true"
        )
        assert response.status_code == expected_status
        return response

    return query_helper


class TestQueryControllers:
    """
    Unit testing for resources/QueryControllers class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    def build_index(self, client, dates):
        """
        build_index Build the index list for query

        Args:
            dates (iterable): list of date strings
        """
        prefix = client.config["PREFIX"]
        idx = prefix + ".v6.run-data."
        index = "/"
        for d in dates:
            index += f"{idx}{d},"
        return index

    def test_missing_json_object(self, client):
        """
        test_missing_json_object Test behavior when no JSON payload is given
        """
        response = client.post(f"{client.config['REST_URI']}/controllers/list")
        assert response.status_code == 400
        assert (
            response.json.get("message") == "QueryControllers: Missing request payload"
        )

    @pytest.mark.parametrize(
        "keys",
        (
            {"user": "x"},
            {"start": "2020"},
            {"end": "2020"},
            {"user": "x", "start": "2020"},
            {"user": "x", "end": "2020"},
            {"start": "2020", "end": "2020"},
        ),
    )
    def test_missing_keys(self, client, keys):
        """
        test_missing_keys Test behavior when JSON payload does not contain
        all required keys.

        Note that "user", "prefix", "start", and "end" are all required;
        however, Pbench will silently ignore any additional keys that are
        specified.
       """
        response = client.post(
            f"{client.config['REST_URI']}/controllers/list", json=keys
        )
        assert response.status_code == 400
        missing = [k for k in ("user", "start", "end") if k not in keys]
        assert (
            response.json.get("message")
            == f"QueryControllers: Missing request data: {','.join(missing)}"
        )

    def test_bad_dates(self, client):
        """
        test_bad_dates Test behavior when a bad date string is given
        """
        response = client.post(
            f"{client.config['REST_URI']}/controllers/list",
            json={
                "user": "drb",
                "prefix": "drb-",
                "start": "2020-15",
                "end": "2020-19",
            },
        )
        assert response.status_code == 400
        assert (
            response.json.get("message")
            == "QueryControllers: Invalid start or end time string"
        )

    def test_query(self, client, query_helper):
        """
        test_query Check the construction of Elasticsearch query URI
        and filtering of the response body.
        """
        json = {
            "user": "drb",
            "start": "2020-08",
            "end": "2020-10",
        }
        response_payload = {
            "took": 1,
            "timed_out": False,
            "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "max_score": None,
                "hits": [],
            },
            "aggregations": {
                "controllers": {
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                    "buckets": [
                        {
                            "key": "unittest-controller1",
                            "doc_count": 2,
                            "runs": {
                                "value": 1.59847315581e12,
                                "value_as_string": "2020-08-26T20:19:15.810Z",
                            },
                        },
                        {
                            "key": "unittest-controller2",
                            "doc_count": 1,
                            "runs": {
                                "value": 1.6,
                                "value_as_string": "2020-09-26T20:19:15.810Z",
                            },
                        },
                    ],
                }
            },
        }

        index = self.build_index(client, ("2020-08", "2020-09", "2020-10"))
        response = query_helper(json, index, 200, json=response_payload)
        res_json = response.json
        assert isinstance(res_json, list)
        assert len(res_json) == 2
        assert res_json[0]["key"] == "unittest-controller1"
        assert res_json[0]["controller"] == "unittest-controller1"
        assert res_json[0]["results"] == 2
        assert res_json[0]["last_modified_value"] == 1.59847315581e12
        assert res_json[0]["last_modified_string"] == "2020-08-26T20:19:15.810Z"
        assert res_json[1]["key"] == "unittest-controller2"
        assert res_json[1]["controller"] == "unittest-controller2"
        assert res_json[1]["results"] == 1
        assert res_json[1]["last_modified_value"] == 1.6
        assert res_json[1]["last_modified_string"] == "2020-09-26T20:19:15.810Z"

    @pytest.mark.parametrize(
        "exceptions",
        (
            {"exception": requests.exceptions.HTTPError, "status": 500},
            {"exception": requests.exceptions.ConnectionError, "status": 502},
            {"exception": requests.exceptions.Timeout, "status": 504},
            {"exception": requests.exceptions.InvalidURL, "status": 500},
            {"exception": Exception, "status": 500},
        ),
    )
    def test_http_error(self, client, query_helper, exceptions):
        """
        test_http_error Check that an Elasticsearch error is reported
        correctly.
       """
        json = {
            "user": "drb",
            "start": "2020-08",
            "end": "2020-08",
        }
        index = self.build_index(client, ("2020-08",))
        query_helper(json, index, exceptions["status"], exc=exceptions["exception"])
