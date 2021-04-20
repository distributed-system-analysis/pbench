import socket
from pathlib import Path

import pytest
from werkzeug.utils import secure_filename

from pbench.server.database.models.tracker import Dataset, States
from pbench.test.unit.server.test_user_auth import login_user, register_user


def get_pbench_token(client, server_config):
    # First create a user
    response = register_user(
        client,
        server_config,
        username="user",
        firstname="firstname",
        lastname="lastName",
        email="user@domain.com",
        password="12345",
    )
    assert response.status_code, 201

    # Login user to get valid pbench token
    response = login_user(client, server_config, "user", "12345")
    assert response.status_code == 200
    data = response.json
    assert data["auth_token"]
    return data["auth_token"]


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
        assert response.json.get("message") == "Invalid request payload"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"

    @staticmethod
    def test_empty_url_path(client, caplog, server_config):
        response = client.post(
            f"{server_config.rest_uri}/elasticsearch", json={"indices": ""}
        )
        assert response.status_code == 400
        assert response.json.get("message") == "Missing required parameters: indices"
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
    def test_missing_authorization_header(client, caplog, server_config):
        response = client.put(
            f"{server_config.rest_uri}/upload/ctrl/{socket.gethostname()}",
            headers={"filename": "f.tar.xz"},
        )
        assert response.status_code == 401
        for record in caplog.records:
            assert record.levelname not in ("ERROR", "CRITICAL")

    @staticmethod
    def test_malformed_authorization_header(client, caplog, server_config):
        response = client.put(
            f"{server_config.rest_uri}/upload/ctrl/{socket.gethostname()}",
            headers={"filename": "f.tar.xz", "Authorization": "Bearer " + "malformed"},
        )
        assert response.status_code == 401
        for record in caplog.records:
            assert record.levelname not in ("ERROR", "CRITICAL")

    @staticmethod
    def test_missing_filename_header_upload(client, caplog, server_config):
        with client:
            auth_token = get_pbench_token(client, server_config)

            expected_message = (
                "Missing filename header, "
                "POST operation requires a filename header to name the uploaded file"
            )
            response = client.put(
                f"{server_config.rest_uri}/upload/ctrl/{socket.gethostname()}",
                headers={"Authorization": "Bearer " + auth_token},
            )
            assert response.status_code == 400
            assert response.json.get("message") == expected_message
            for record in caplog.records:
                assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")

    @staticmethod
    def test_missing_md5sum_header_upload(client, caplog, server_config):
        with client:
            auth_token = get_pbench_token(client, server_config)

            expected_message = "Missing md5sum header, POST operation requires md5sum of an uploaded file in header"
            response = client.put(
                f"{server_config.rest_uri}/upload/ctrl/{socket.gethostname()}",
                headers={
                    "Authorization": "Bearer " + auth_token,
                    "filename": "f.tar.xz",
                },
            )
            assert response.status_code == 400
            assert response.json.get("message") == expected_message
            for record in caplog.records:
                assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")

    @staticmethod
    def test_mismatched_md5sum_header(client, caplog, server_config):
        with client:
            auth_token = get_pbench_token(client, server_config)

            filename = "log.tar.xz"
            datafile = Path("./lib/pbench/test/unit/server/fixtures/upload/", filename)
            controller = socket.gethostname()

            with open(datafile, "rb") as data_fp:
                response = client.put(
                    f"{server_config.rest_uri}/upload/ctrl/{controller}",
                    data=data_fp,
                    headers={
                        "Authorization": "Bearer " + auth_token,
                        "filename": filename,
                        "Content-MD5": "md5sum",  # Wrong md5 hash
                    },
                )
            assert response.status_code == 400
            assert (
                response.json.get("message")
                == f"md5sum check failed for {filename}, upload failed"
            )

    @staticmethod
    @pytest.mark.parametrize("bad_extension", ("test.tar.bad", "test.tar", "test.tar."))
    def test_bad_extension_upload(client, bad_extension, caplog, server_config):
        with client:
            auth_token = get_pbench_token(client, server_config)

            expected_message = "File extension not supported. Only .xz"
            response = client.put(
                f"{server_config.rest_uri}/upload/ctrl/{socket.gethostname()}",
                headers={
                    "Authorization": "Bearer " + auth_token,
                    "filename": bad_extension,
                    "Content-MD5": "md5sum",
                },
            )
            assert response.status_code == 400
            assert response.json.get("message") == expected_message
            for record in caplog.records:
                assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")

    @staticmethod
    def test_invalid_authorization_upload(client, caplog, server_config):
        with client:
            auth_token = get_pbench_token(client, server_config)
            # Log the token out
            response = client.post(
                f"{server_config.rest_uri}/logout",
                headers={"Authorization": "Bearer " + auth_token},
            )

            # Upload with invalid token
            response = client.put(
                f"{server_config.rest_uri}/upload/ctrl/{socket.gethostname()}",
                headers={
                    "Authorization": "Bearer " + auth_token,
                    "Content-MD5": "md5sum",
                },
            )
            assert response.status_code == 401

    @staticmethod
    def test_empty_upload(client, pytestconfig, caplog, server_config):
        with client:
            auth_token = get_pbench_token(client, server_config)

            expected_message = "Upload failed, Content-Length received in header is 0"
            filename = "tmp.tar.xz"
            tmp_d = pytestconfig.cache.get("TMP", None)
            Path(tmp_d, filename).touch()

            with open(Path(tmp_d, filename), "rb") as data_fp:
                response = client.put(
                    f"{server_config.rest_uri}/upload/ctrl/{socket.gethostname()}",
                    data=data_fp,
                    headers={
                        "Authorization": "Bearer " + auth_token,
                        "filename": filename,
                        "Content-MD5": "d41d8cd98f00b204e9800998ecf8427e",  # MD5 hash of an empty file
                    },
                )
            assert response.status_code == 400
            assert response.json.get("message") == expected_message
            for record in caplog.records:
                assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")

    @staticmethod
    def test_upload(client, pytestconfig, caplog, server_config):
        with client:
            auth_token = get_pbench_token(client, server_config)

            filename = "log.tar.xz"
            datafile = Path("./lib/pbench/test/unit/server/fixtures/upload/", filename)
            controller = socket.gethostname()
            with open(f"{datafile}.md5") as md5sum_check:
                md5sum = md5sum_check.read()

            with open(datafile, "rb") as data_fp:
                response = client.put(
                    f"{server_config.rest_uri}/upload/ctrl/{controller}",
                    data=data_fp,
                    headers={
                        "Authorization": "Bearer " + auth_token,
                        "filename": filename,
                        "Content-MD5": md5sum,
                    },
                )

            assert response.status_code == 201, repr(response)
            sfilename = secure_filename(filename)
            tmp_d = pytestconfig.cache.get("TMP", None)
            receive_dir = Path(
                tmp_d, "srv", "pbench", "pbench-move-results-receive", "fs-version-002"
            )
            assert receive_dir.exists(), (
                f"receive_dir = '{receive_dir}', filename = '{filename}',"
                f" sfilename = '{sfilename}'"
            )

            dataset = Dataset.attach(controller=controller, path=filename)
            assert dataset is not None
            assert dataset.md5 == md5sum
            assert dataset.controller == controller
            assert dataset.name == "log"
            assert dataset.state == States.UPLOADED

            for record in caplog.records:
                assert record.levelname not in ("WARNING", "ERROR", "CRITICAL")
