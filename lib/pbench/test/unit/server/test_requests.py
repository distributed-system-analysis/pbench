import os
import socket
import pytest

from pathlib import Path
from werkzeug.utils import secure_filename


class TestHostInfo:
    @staticmethod
    def test_host_info(client, pytestconfig, caplog, server_config):
        tmp_d = pytestconfig.cache.get("TMP", None)
        expected_message = (
            f"pbench@pbench.example.com:{tmp_d}/srv/pbench"
            "/pbench-move-results-receive"
            "/fs-version-002"
        )
        response = client.get(f"{server_config.rest_uri}/host_info")

        assert response.status_code == 200
        assert response.json.get("message") == expected_message
        for record in caplog.records:
            assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")


class TestElasticsearch:
    @staticmethod
    def test_json_object(client, caplog, server_config):
        response = client.post(f"{server_config.rest_uri}/elasticsearch")
        assert response.status_code == 400
        assert response.json.get("message") == "Invalid json object in the query"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"

    @staticmethod
    def test_empty_url_path(client, caplog, server_config):
        response = client.post(
            f"{server_config.rest_uri}/elasticsearch", json={"indices": ""}
        )
        assert response.status_code == 400
        assert (
            response.json.get("message") == "Missing indices path in the post request"
        )
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"

    @staticmethod
    def test_bad_request(client, caplog, server_config, requests_mock):
        requests_mock.post(
            "http://elasticsearch.example.com:7080/some_invalid_url", status_code=400
        )
        response = client.post(
            f"{server_config.rest_uri}/elasticsearch",
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
    def test_json_object(client, caplog, server_config):
        response = client.post(f"{server_config.rest_uri}/graphql")
        assert response.status_code == 400
        assert response.json.get("message") == "Invalid json object"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"


class TestUpload:
    @staticmethod
    def test_missing_filename_header_upload(client, caplog, server_config):
        expected_message = (
            "Missing filename header, "
            "POST operation requires a filename header to name the uploaded file"
        )
        response = client.put(
            f"{server_config.rest_uri}/upload/ctrl/{socket.gethostname()}"
        )
        assert response.status_code == 400
        assert response.json.get("message") == expected_message
        for record in caplog.records:
            assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")

    @staticmethod
    def test_missing_md5sum_header_upload(client, caplog, server_config):
        expected_message = "Missing md5sum header, POST operation requires md5sum of an uploaded file in header"
        response = client.put(
            f"{server_config.rest_uri}/upload/ctrl/{socket.gethostname()}",
            headers={"filename": "f.tar.xz"},
        )
        assert response.status_code == 400
        assert response.json.get("message") == expected_message
        for record in caplog.records:
            assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")

    @staticmethod
    @pytest.mark.parametrize("bad_extension", ("test.tar.bad", "test.tar", "test.tar."))
    def test_bad_extension_upload(client, bad_extension, caplog, server_config):
        expected_message = "File extension not supported. Only .xz"
        response = client.put(
            f"{server_config.rest_uri}/upload/ctrl/{socket.gethostname()}",
            headers={"filename": bad_extension, "Content-MD5": "md5sum"},
        )
        assert response.status_code == 400
        assert response.json.get("message") == expected_message
        for record in caplog.records:
            assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")

    @staticmethod
    def test_empty_upload(client, pytestconfig, caplog, server_config):
        expected_message = "Upload failed, Content-Length received in header is 0"
        filename = "tmp.tar.xz"
        tmp_d = pytestconfig.cache.get("TMP", None)
        Path(tmp_d, filename).touch()

        with open(Path(tmp_d, filename), "rb") as data_fp:
            response = client.put(
                f"{server_config.rest_uri}/upload/ctrl/{socket.gethostname()}",
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
    def test_upload(client, pytestconfig, caplog, server_config):
        filename = "log.tar.xz"
        datafile = Path("./lib/pbench/test/unit/server/fixtures/upload/", filename)

        with open(f"{datafile}.md5") as md5sum_check:
            md5sum = md5sum_check.read()

        with open(datafile, "rb") as data_fp:
            response = client.put(
                f"{server_config.rest_uri}/upload/ctrl/{socket.gethostname()}",
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
