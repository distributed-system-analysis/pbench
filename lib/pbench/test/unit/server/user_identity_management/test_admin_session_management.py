import logging

import responses
from click.testing import CliRunner

from pbench.cli.server.session_management import get_user_sessions
from pbench.server.auth.keycloak_admin import Admin


class TestKeycloakAdminUserSessionManagement:
    USER_ID = "12345"
    USERNAME = "test"
    REALM = "test_realm"
    ADMIN_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJDeXVpZDFYU2F3"

    @staticmethod
    def test_help():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(get_user_sessions, ["--help"])
        assert result.exit_code == 0, result.stderr
        assert str(result.stdout).startswith("Usage:")

    @responses.activate
    def test_get_all_user_sessions_with_user_id(self, caplog, server_config):
        responses.add(
            responses.GET,
            "http://pbench.example.com/admin/realms/test_realm/users/12345/sessions",
            status=200,
            body='[{"id": "185481e0-dc03-41ee-be64-19b569a580f5", "username": "test", '
            '"usderId": "facc323e-5228-42bd-bc74-9f5f402176a2", "ipAdress": "10.22.18.174", '
            '"start": 1659394065000, "lastAccess": 1659394065000, '
            '"clients": {"d98aa03e-a258-446b-8ebd-9d91116a8d8f": "account-console"}}]',
            content_type="application/json",
        )

        runner = CliRunner(mix_stderr=False)
        caplog.set_level(logging.DEBUG)

        result = runner.invoke(
            get_user_sessions,
            args=[
                "--user_id",
                self.USER_ID,
                "--realm",
                self.REALM,
                "--admin_token",
                self.ADMIN_TOKEN,
            ],
        )
        assert result.exit_code == 0, result.stderr

    @responses.activate
    def test_get_all_user_sessions_with_username(
        self, monkeypatch, caplog, server_config
    ):
        responses.add(
            responses.GET,
            "http://pbench.example.com/admin/realms/test_realm/users/12345/sessions",
            status=200,
            body='[{"id": "185481e0-dc03-41ee-be64-19b569a580f5", "username": "test", '
            '"usderId": "facc323e-5228-42bd-bc74-9f5f402176a2", "ipAdress": "10.22.18.174", '
            '"start": 1659394065000, "lastAccess": 1659394065000, '
            '"clients": {"d98aa03e-a258-446b-8ebd-9d91116a8d8f": "account-console"}}]',
            content_type="application/json",
        )

        def mockuser_id(self, username):
            return TestKeycloakAdminUserSessionManagement.USER_ID

        monkeypatch.setattr(Admin, "get_user_id", mockuser_id)

        runner = CliRunner(mix_stderr=False)
        caplog.set_level(logging.INFO)

        result = runner.invoke(
            get_user_sessions,
            args=[
                "--username",
                self.USERNAME,
                "--realm",
                self.REALM,
                "--admin_token",
                self.ADMIN_TOKEN,
            ],
        )
        assert result.exit_code == 0, result.stderr

    @responses.activate
    def test_get_all_user_sessions_without_user(self, caplog, server_config):
        runner = CliRunner(mix_stderr=False)
        caplog.set_level(logging.INFO)

        result = runner.invoke(
            get_user_sessions,
            args=["--realm", "test_realm", "--admin_token", self.ADMIN_TOKEN],
        )
        assert result.exit_code == 1, (
            result.stderr == "Either username or user_id is required"
        )
