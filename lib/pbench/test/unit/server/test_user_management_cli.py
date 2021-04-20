import datetime

import responses
from click.testing import CliRunner

from pbench.cli.server.user_management import (
    user_create,
    user_delete,
    user_list,
    user_update,
)


class TestUserManagement:
    USER_SWITCH = "--username"
    PSWD_SWITCH = "--password"
    PSWD_PROMPT = "Password: "
    EMAIL_SWITCH = "--email"
    FIRST_NAME_SWITCH = "--first-name"
    LAST_NAME_SWITCH = "--last-name"
    ROLE_SWITCH = "--role"
    USER_TEXT = "test_user"
    PSWD_TEXT = "password"
    EMAIL_TEXT = "test@domain.com"
    FIRST_NAME_TEXT = "First"
    LAST_NAME_TEXT = "Last"
    URL = "http://pbench.example.com/api/v1"
    ENDPOINT = "/register"

    @staticmethod
    @responses.activate
    def test_help(pytestconfig):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(user_create, ["--help"])
        assert result.exit_code == 0
        assert str(result.stdout).startswith("Usage:")
        assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_args(server_config, pytestconfig):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            user_create,
            args=[
                TestUserManagement.USER_SWITCH,
                TestUserManagement.USER_TEXT,
                TestUserManagement.PSWD_SWITCH,
                TestUserManagement.PSWD_TEXT,
                TestUserManagement.EMAIL_SWITCH,
                TestUserManagement.EMAIL_TEXT,
                TestUserManagement.FIRST_NAME_SWITCH,
                TestUserManagement.FIRST_NAME_TEXT,
                TestUserManagement.LAST_NAME_SWITCH,
                TestUserManagement.LAST_NAME_TEXT,
            ],
        )
        assert result.stdout_bytes == b"User test_user registered\n"
        assert result.exit_code == 0
        assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_valid_user_registration(client, server_config, pytestconfig):
        with client:
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                user_create,
                args=[
                    TestUserManagement.USER_SWITCH,
                    TestUserManagement.USER_TEXT,
                    TestUserManagement.EMAIL_SWITCH,
                    TestUserManagement.EMAIL_TEXT,
                    TestUserManagement.FIRST_NAME_SWITCH,
                    TestUserManagement.FIRST_NAME_TEXT,
                    TestUserManagement.LAST_NAME_SWITCH,
                    TestUserManagement.LAST_NAME_TEXT,
                ],
                input=f"{TestUserManagement.PSWD_TEXT}\n",
            )
            assert result.exit_code == 0
            assert (
                result.stdout
                == f"{TestUserManagement.PSWD_PROMPT}\n" + "User test_user registered\n"
            )
            assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_admin_user_creation(client, server_config, pytestconfig):
        with client:
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                user_create,
                args=[
                    TestUserManagement.USER_SWITCH,
                    TestUserManagement.USER_TEXT,
                    TestUserManagement.PSWD_SWITCH,
                    TestUserManagement.PSWD_TEXT,
                    TestUserManagement.EMAIL_SWITCH,
                    TestUserManagement.EMAIL_TEXT,
                    TestUserManagement.FIRST_NAME_SWITCH,
                    TestUserManagement.FIRST_NAME_TEXT,
                    TestUserManagement.LAST_NAME_SWITCH,
                    TestUserManagement.LAST_NAME_TEXT,
                    TestUserManagement.ROLE_SWITCH,
                    "ADMIN",
                ],
            )
            assert result.exit_code == 0
            assert result.stdout == "Admin user test_user registered\n"
            assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_user_creation_with_invalid_role(client, server_config, pytestconfig):
        with client:
            runner = CliRunner(mix_stderr=False)
            result = runner.invoke(
                user_create,
                args=[
                    TestUserManagement.USER_SWITCH,
                    TestUserManagement.USER_TEXT,
                    TestUserManagement.PSWD_SWITCH,
                    TestUserManagement.PSWD_TEXT,
                    TestUserManagement.EMAIL_SWITCH,
                    TestUserManagement.EMAIL_TEXT,
                    TestUserManagement.FIRST_NAME_SWITCH,
                    TestUserManagement.FIRST_NAME_TEXT,
                    TestUserManagement.LAST_NAME_SWITCH,
                    TestUserManagement.LAST_NAME_TEXT,
                    TestUserManagement.ROLE_SWITCH,
                    "ADMN",
                ],
            )
            assert result.exit_code == 2

    @staticmethod
    @responses.activate
    def test_valid_user_delete(client, server_config, pytestconfig):
        with client:
            runner = CliRunner(mix_stderr=False)
            TestUserManagement.test_args(server_config, pytestconfig)

            result = runner.invoke(user_delete, args=[TestUserManagement.USER_TEXT])
            assert result.exit_code == 0
            assert result.stdout == "User test_user deleted\n"
            assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_invalid_user_delete(client, server_config, pytestconfig):
        with client:
            runner = CliRunner(mix_stderr=False)
            # Give username that doesn't exists to delete
            result = runner.invoke(user_delete, args=["wrong_username"])
            assert result.exit_code == 1
            assert result.stdout == "User wrong_username does not exists\n"
            assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_valid_user_list(client, server_config, pytestconfig):
        with client:
            runner = CliRunner(mix_stderr=False)
            TestUserManagement.test_args(server_config, pytestconfig)

            result = runner.invoke(user_list,)
            row_format = "{0:15}\t{1:15}\t{2:15}\t{3:15}\t{4:20}"
            assert result.exit_code == 0
            assert (
                result.stdout
                == row_format.format(
                    "Username", "First Name", "Last Name", "Registered On", "Email"
                )
                + "\n"
                + row_format.format(
                    TestUserManagement.USER_TEXT,
                    TestUserManagement.FIRST_NAME_TEXT,
                    TestUserManagement.LAST_NAME_TEXT,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                    TestUserManagement.EMAIL_TEXT,
                )
                + "\n"
            )
            assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_valid_user_update(client, server_config, pytestconfig):
        with client:
            runner = CliRunner(mix_stderr=False)
            TestUserManagement.test_args(server_config, pytestconfig)

            # Update email field
            result = runner.invoke(
                user_update,
                args=[
                    TestUserManagement.USER_TEXT,
                    TestUserManagement.EMAIL_SWITCH,
                    "new_test@domain.com",
                ],
            )
            assert result.exit_code == 0
            assert result.stdout == "User test_user updated\n"
            assert not result.stderr_bytes

            # Update valid role of the user
            result = runner.invoke(
                user_update,
                args=[
                    TestUserManagement.USER_TEXT,
                    TestUserManagement.ROLE_SWITCH,
                    "ADMIN",
                ],
            )
            assert result.exit_code == 0
            assert result.stdout == "User test_user updated\n"
            assert not result.stderr_bytes

            # Update invalid role of the user
            result = runner.invoke(
                user_update,
                args=[
                    TestUserManagement.USER_TEXT,
                    TestUserManagement.ROLE_SWITCH,
                    "ADMN",
                ],
            )
            assert result.exit_code == 2
            assert (
                result.stderr_bytes
                == b"Usage: user-update [OPTIONS] UPDATEUSER\nTry 'user-update --help' for help.\n"
                + b"\nError: Invalid value for '--role': invalid choice: ADMN. (choose from ADMIN)\n"
            )

    @staticmethod
    @responses.activate
    def test_invalid_user_update(client, server_config, pytestconfig):
        with client:
            runner = CliRunner(mix_stderr=False)

            # Update with non-existent username
            result = runner.invoke(
                user_update,
                args=[
                    TestUserManagement.USER_TEXT,
                    TestUserManagement.EMAIL_SWITCH,
                    "new_test@domain.com",
                ],
            )
            assert result.exit_code == 1
            assert (
                result.stdout
                == f"No such a user {TestUserManagement.USER_TEXT} to update\n"
            )
            assert not result.stderr_bytes
