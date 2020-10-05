import os

import pytest
from werkzeug.utils import secure_filename
from pathlib import Path


class TestHostInfo:
    @staticmethod
    def test_host_info(client, pytestconfig):
        tmp_d = pytestconfig.cache.get("TMP", None)
        expected_message = (
            f"pbench@pbench.example.com:{tmp_d}/srv/pbench"
            "/pbench-move-results-receive"
            "/fs-version-002"
        )
        response = client.get(f"{client.config['REST_URI']}/host_info")

        assert response.status_code == 200
        assert response.json.get("message") == expected_message


class TestElasticsearch:
    @staticmethod
    def test_json_object(client):
        response = client.post(f"{client.config['REST_URI']}/elasticsearch")
        assert response.status_code == 400
        assert (
            response.json.get("message")
            == "Elasticsearch: Invalid json object in request"
        )

    @staticmethod
    def test_empty_url_path(client):
        response = client.post(
            f"{client.config['REST_URI']}/elasticsearch", json={"indices": ""}
        )
        assert response.status_code == 400
        assert (
            response.json.get("message")
            == "Missing indices path in the Elasticsearch request"
        )

    @staticmethod
    def test_bad_request(client):
        response = client.post(
            f"{client.config['REST_URI']}/elasticsearch",
            json={"indices": "some_invalid_url"},
        )
        assert response.status_code == 500
        assert (
            response.json.get("message") == "Could not post to Elasticsearch endpoint"
        )


class TestGraphQL:
    @staticmethod
    def test_json_object(client):
        response = client.post(f"{client.config['REST_URI']}/graphql")
        assert response.status_code == 400
        assert response.json.get("message") == "GraphQL: Invalid json object in request"


class TestUpload:
    @staticmethod
    def test_missing_filename_header_upload(client):
        expected_message = (
            "Missing filename header, "
            "POST operation requires a filename header to name the uploaded file"
        )
        response = client.post(f"{client.config['REST_URI']}/upload")
        assert response.status_code == 400
        assert response.json.get("message") == expected_message

    @staticmethod
    def test_missing_md5sum_header_upload(client):
        expected_message = "Missing md5sum header, POST operation requires md5sum of an uploaded file in header"
        response = client.post(
            f"{client.config['REST_URI']}/upload", headers={"filename": "f.tar.xz"}
        )
        assert response.status_code == 400
        assert response.json.get("message") == expected_message

    @staticmethod
    @pytest.mark.parametrize("bad_extension", ("test.tar.bad", "test.tar", "test.tar."))
    def test_bad_extension_upload(client, bad_extension):
        expected_message = "File extension not supported. Only .xz"
        response = client.post(
            f"{client.config['REST_URI']}/upload",
            headers={"filename": bad_extension, "md5sum": "md5sum"},
        )
        assert response.status_code == 400
        assert response.json.get("message") == expected_message

    @staticmethod
    def test_empty_upload(client, pytestconfig):
        expected_message = "Upload failed, Content-Length received in header is 0"
        filename = "tmp.tar.xz"
        tmp_d = pytestconfig.cache.get("TMP", None)
        Path(tmp_d, filename).touch()

        with open(Path(tmp_d, filename), "rb") as data_fp:
            response = client.post(
                f"{client.config['REST_URI']}/upload",
                data=data_fp,
                headers={
                    "filename": "log.tar.xz",
                    "md5sum": "d41d8cd98f00b204e9800998ecf8427e",
                },
            )
        assert response.status_code == 400
        assert response.json.get("message") == expected_message

    @staticmethod
    def test_upload(client, pytestconfig):
        filename = "log.tar.xz"
        datafile = Path("./lib/pbench/test/unit/server/fixtures/upload/", filename)

        with open(f"{datafile}.md5") as md5sum_check:
            md5sum = md5sum_check.read()

        with open(datafile, "rb") as data_fp:
            response = client.post(
                f"{client.config['REST_URI']}/upload",
                data=data_fp,
                headers={"filename": filename, "md5sum": md5sum},
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
