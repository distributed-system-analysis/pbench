import os

import pytest
from werkzeug.utils import secure_filename


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


class TestDownload:
    @staticmethod
    def test_json_object(client):
        response = client.post(f"{client.config['REST_URI']}/elasticsearch")
        assert response.status_code == 400
        assert response.json.get("message") == "Invalid json object in request"

    @staticmethod
    def test_empty_url_path(client):
        response = client.post(
            f"{client.config['REST_URI']}/elasticsearch", json={"indices": ""}
        )
        assert response.status_code == 400
        assert response.json.get("message") == "Missing path in request"

    @staticmethod
    def test_invalid_url_path(client):
        response = client.post(
            f"{client.config['REST_URI']}/elasticsearch",
            json={"indices": "some_invalid_url"},
        )
        assert response.status_code == 500
        assert (
            response.json.get("message")
            == "There was something wrong with your download request"
        )


class TestGraphQL:
    @staticmethod
    def test_json_object(client):
        response = client.post(f"{client.config['REST_URI']}/graphql")
        assert response.status_code == 400
        assert response.json.get("message") == "Invalid query object in request"


class TestUpload:
    @staticmethod
    def test_missing_filename_header_upload(client):
        expected_message = "Missing filename header in request"
        response = client.post(f"{client.config['REST_URI']}/upload")
        assert response.status_code == 400
        assert response.json.get("message") == expected_message

    @staticmethod
    def test_missing_md5sum_header_upload(client):
        expected_message = "Missing md5sum header in request"
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
    def test_upload(client, pytestconfig):
        filename = "./lib/pbench/test/unit/server/fixtures/upload/log.tar.xz"

        with open(f"{filename}.md5") as md5sum_check:
            md5sum = md5sum_check.read()

        response = client.post(
            f"{client.config['REST_URI']}/upload",
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
