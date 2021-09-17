import hashlib
import socket
from http import HTTPStatus
from pathlib import Path

import pytest

from freezegun import freeze_time

from pbench.server.database.models.datasets import Dataset, States, Metadata
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
    assert response.status_code == HTTPStatus.CREATED

    # Login user to get valid pbench token
    response = login_user(client, server_config, "user", "12345")
    assert response.status_code == HTTPStatus.OK
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

        assert response.status_code == HTTPStatus.OK
        assert response.json.get("message") == expected_message
        for record in caplog.records:
            assert record.levelname == "INFO"


class TestElasticsearch:
    @staticmethod
    def test_missing_json_object(client, caplog, server_config, pbench_token):
        response = client.post(
            f"{server_config.rest_uri}/elasticsearch",
            headers={"Authorization": "Bearer " + pbench_token},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == "Invalid request payload"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"

    @staticmethod
    def test_empty_url_path(client, caplog, server_config, pbench_token):
        response = client.post(
            f"{server_config.rest_uri}/elasticsearch",
            json={"indices": None},
            headers={"Authorization": "Bearer " + pbench_token},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == "Missing required parameters: indices"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"

    @staticmethod
    def test_bad_request(client, caplog, server_config, requests_mock, pbench_token):
        requests_mock.post(
            "http://elasticsearch.example.com:7080/some_invalid_url",
            status_code=HTTPStatus.BAD_REQUEST,
        )
        response = client.post(
            f"{server_config.rest_uri}/elasticsearch",
            headers={"Authorization": "Bearer " + pbench_token},
            json={"indices": "some_invalid_url", "payload": '{ "babble": "42" }'},
        )
        assert response.status_code == HTTPStatus.BAD_GATEWAY


class TestGraphQL:
    @staticmethod
    def test_json_object(client, caplog, server_config):
        response = client.post(f"{server_config.rest_uri}/graphql")
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == "Invalid json object"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "WARNING"


class TestUpload:
    @pytest.fixture
    def setup_ctrl(self):
        self.controller = socket.gethostname()
        yield
        self.controller = None

    @staticmethod
    def gen_uri(server_config, filename="f.tar.xz"):
        return f"{server_config.rest_uri}/upload/{filename}"

    def gen_headers(self, auth_token, md5):
        headers = {
            "Authorization": "Bearer " + auth_token,
            "controller": self.controller,
            "Content-MD5": md5,
        }
        return headers

    @staticmethod
    def verify_logs(caplog):
        for record in caplog.records:
            assert record.levelname not in ("DEBUG", "ERROR", "CRITICAL")
        assert caplog.records[-1].levelname == "WARNING"

    def test_missing_authorization_header(self, client, caplog, server_config):
        response = client.put(self.gen_uri(server_config))
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        self.verify_logs(caplog)

    @pytest.mark.parametrize(
        "malformed_token", ("malformed", "bear token" "Bearer malformed"),
    )
    def test_malformed_authorization_header(
        self, client, caplog, server_config, malformed_token
    ):
        response = client.put(
            self.gen_uri(server_config), headers={"Authorization": malformed_token},
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        self.verify_logs(caplog)

    def test_missing_controller_header_upload(
        self, client, caplog, server_config, pbench_token
    ):
        expected_message = "Missing required controller header"
        response = client.put(
            self.gen_uri(server_config),
            headers={"Authorization": "Bearer " + pbench_token},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)

    def test_missing_md5sum_header_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_token
    ):
        expected_message = "Missing required Content-MD5 header"
        response = client.put(
            self.gen_uri(server_config),
            headers={
                "Authorization": "Bearer " + pbench_token,
                "controller": self.controller,
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)

    def test_missing_length_header_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_token
    ):
        expected_message = "Missing required Content-Length header"
        response = client.put(
            self.gen_uri(server_config),
            headers={
                "Authorization": "Bearer " + pbench_token,
                "controller": self.controller,
                "Content-MD5": "ANYMD5",
            },
        )
        assert response.status_code == HTTPStatus.LENGTH_REQUIRED
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)

    def test_mismatched_md5sum_header(
        self, client, caplog, server_config, setup_ctrl, pbench_token
    ):
        filename = "log.tar.xz"
        datafile = Path("./lib/pbench/test/unit/server/fixtures/upload/", filename)

        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, filename),
                data=data_fp,
                # Content-Length header set automatically
                headers=self.gen_headers(pbench_token, "md5sum"),
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message").startswith(
            "MD5 checksum does not match Content-MD5 header"
        )
        self.verify_logs(caplog)

    @pytest.mark.parametrize("bad_extension", ("test.tar.bad", "test.tar", "test.tar."))
    def test_bad_extension_upload(
        self,
        client,
        bad_extension,
        pytestconfig,
        caplog,
        server_config,
        setup_ctrl,
        pbench_token,
    ):
        expected_message = "File extension not supported, must be .tar.xz"
        tmp_d = pytestconfig.cache.get("TMP", None)
        datafile = Path(tmp_d, bad_extension)
        datafile.write_text("compressed tar ball")
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, bad_extension),
                data=data_fp,
                # Content-Length header set automatically
                headers=self.gen_headers(pbench_token, "md5sum"),
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)

    def test_invalid_authorization_upload(
        self, client, caplog, server_config, setup_ctrl, pbench_token
    ):
        # Log out the user
        response = client.post(
            f"{server_config.rest_uri}/logout",
            headers={"Authorization": "Bearer " + pbench_token},
        )

        # Upload with invalid token
        response = client.put(
            self.gen_uri(server_config),
            headers=self.gen_headers(pbench_token, "md5sum"),
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        for record in caplog.records:
            assert record.levelname in ["DEBUG", "INFO"]

    def test_empty_upload(
        self, client, pytestconfig, caplog, server_config, setup_ctrl, pbench_token
    ):
        expected_message = (
            "Content-Length (0) must be greater than 0 and no greater than 1.1 GB"
        )
        filename = "tmp.tar.xz"
        tmp_d = pytestconfig.cache.get("TMP", None)
        datafile = Path(tmp_d, filename)
        datafile.touch()
        with datafile.open("rb") as data_fp:
            response = client.put(
                self.gen_uri(server_config, filename),
                data=data_fp,
                # Content-Length header set automatically
                # MD5 hash of an empty file
                headers=self.gen_headers(
                    pbench_token, "d41d8cd98f00b204e9800998ecf8427e"
                ),
            )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json.get("message") == expected_message
        self.verify_logs(caplog)

    def test_upload(
        self, client, pytestconfig, caplog, server_config, setup_ctrl, pbench_token
    ):
        # This is a really weird and ugly file name that should be
        # maintained through all the marshalling and unmarshalling on the
        # wire until it lands on disk and in the Dataset.
        filename = "pbench-user-benchmark_some + config_2021.05.01T12.42.42.tar.xz"
        tmp_d = pytestconfig.cache.get("TMP", None)
        datafile = Path(tmp_d, filename)
        file_contents = b"something\n"
        md5 = hashlib.md5()
        md5.update(file_contents)
        datafile.write_bytes(file_contents)

        with datafile.open("rb") as data_fp, freeze_time("1970-01-01"):
            response = client.put(
                self.gen_uri(server_config, filename),
                data=data_fp,
                headers=self.gen_headers(pbench_token, md5.hexdigest()),
            )

        assert response.status_code == HTTPStatus.CREATED, repr(response)
        tmp_d = pytestconfig.cache.get("TMP", None)
        receive_dir = Path(
            tmp_d, "srv", "pbench", "pbench-move-results-receive", "fs-version-002"
        )
        assert (
            receive_dir.exists()
        ), f"receive_dir = '{receive_dir}', filename = '{filename}'"

        dataset = Dataset.attach(controller=self.controller, path=filename)
        assert dataset is not None
        assert dataset.md5 == md5.hexdigest()
        assert dataset.controller == self.controller
        assert dataset.name == filename[:-7]
        assert dataset.state == States.UPLOADED
        assert Metadata.getvalue(dataset, Metadata.DASHBOARD) is None
        assert Metadata.getvalue(dataset, Metadata.DELETION) == "1972-01-01"

        for record in caplog.records:
            assert record.levelname in ["DEBUG", "INFO"]
