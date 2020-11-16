import os
import socket

import pytest
import responses

from pathlib import Path
from werkzeug.utils import secure_filename


@pytest.fixture
def mocked_responses():
    with responses.RequestsMock() as rsps:
        yield rsps


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
    def test_bad_request(client, caplog, mocked_responses):
        mocked_responses.add(
            responses.POST,
            "http://elasticsearch.example.com:7080/some_invalid_url",
            status=400,
        )
        response = client.post(
            f"{client.config['REST_URI']}/elasticsearch",
            json={"indices": "some_invalid_url", "payload": '{ "babble": "42" }'},
        )
        assert response.status_code == 400
        assert response.json is None
        assert len(caplog.records) == 0


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
        datafile = Path("./lib/pbench/test/server/fixtures/upload/", filename)

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
