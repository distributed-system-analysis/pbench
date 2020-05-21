import os

import pytest
from werkzeug.utils import secure_filename

from pbench.test.unit.server.common import (
    filename,
    temp_dir,
)


class TestHostInfo:
    @staticmethod
    def test_host_info(client):
        response = client.get(f"{client.config['REST_URI']}/host_info")
        assert response.status_code == 200
        assert response.json.get("message") == "pbench@pbench.example.com" ":/tmp/-002"


class TestUpload:
    @staticmethod
    def test_missing_filename_header_upload(client):
        response = client.post(f"{client.config['REST_URI']}/upload")
        assert response.status_code == 400
        assert response.json.get("message") == "Missing filename header in request"

    @staticmethod
    def test_missing_md5sum_header_upload(client):
        response = client.post(
            f"{client.config['REST_URI']}/upload", headers={"filename": filename}
        )
        assert response.status_code == 400
        assert response.json.get("message") == "Missing md5sum header in request"

    @staticmethod
    @pytest.mark.parametrize("bad_extension", ("test.tar.bad", "test.tar", "test.tar."))
    def test_bad_extension_upload(client, bad_extension):
        response = client.post(
            f"{client.config['REST_URI']}/upload",
            headers={"filename": bad_extension, "md5sum": "md5sum"},
        )
        assert response.status_code == 400
        assert response.json.get("message") == "File extension not supported. Only .xz"

    @staticmethod
    def test_upload(client):
        with open(f"{filename}.md5.check") as md5sum_check:
            md5sum = md5sum_check.read()

        response = client.post(
            f"{client.config['REST_URI']}/upload",
            headers={"filename": filename, "md5sum": md5sum},
        )
        assert response.status_code == 201
        assert os.path.exists(os.path.join(temp_dir, secure_filename(filename)))
