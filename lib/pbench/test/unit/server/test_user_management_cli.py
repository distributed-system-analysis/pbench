import datetime

import pytest
import responses
from click.testing import CliRunner

from pbench.cli.server.user_management import (
    USER_LIST_HEADER_ROW,
    USER_LIST_ROW_FORMAT,
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
    def register_user(server_config, pytestconfig):
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
        return result

    @staticmethod
    @responses.activate
    def test_valid_user_registration_with_password_input(client, server_config, pytestconfig):
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
            assert result.exit_code == 0, result.stderr
            assert (
                result.stdout
                == f"{TestUserManagement.PSWD_PROMPT}\n" + "User test_user registered\n"
            )

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
            assert result.exit_code == 0, result.stderr
            assert result.stdout == "Admin user test_user registered\n"

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
            assert (
                result.stderr_bytes
                == b"Usage: user-create [OPTIONS]\nTry 'user-create --help' for help.\n"
                + b"\nError: Invalid value for '--role': invalid choice: ADMN. (choose from ADMIN)\n"
            )

    @staticmethod
    @responses.activate
    def test_valid_user_delete(client, server_config, pytestconfig):
        with client:
            runner = CliRunner(mix_stderr=False)
            result = TestUserManagement.register_user(server_config, pytestconfig)
            assert result.exit_code == 0, result.stderr

            result = runner.invoke(user_delete, args=[TestUserManagement.USER_TEXT])
            assert result.exit_code == 0, result.stderr
            assert result.stdout == "User test_user deleted\n"

    @staticmethod
    @responses.activate
    def test_invalid_user_delete(client, server_config, pytestconfig):
        with client:
            runner = CliRunner(mix_stderr=False)
            # Give username that doesn't exists to delete
            result = runner.invoke(user_delete, args=["wrong_username"])
            assert result.exit_code == 1
            assert result.stderr == "User wrong_username does not exist\n"

    @staticmethod
    @responses.activate
    def test_valid_user_list(client, server_config, pytestconfig):
        with client:
            runner = CliRunner(mix_stderr=False)
            result = TestUserManagement.register_user(server_config, pytestconfig)
            assert result.exit_code == 0, result.stderr

            result = runner.invoke(user_list,)
            assert result.exit_code == 0, result.stderr
            assert (
                result.stdout
                == USER_LIST_HEADER_ROW
                + "\n"
                + USER_LIST_ROW_FORMAT.format(
                    TestUserManagement.USER_TEXT,
                    TestUserManagement.FIRST_NAME_TEXT,
                    TestUserManagement.LAST_NAME_TEXT,
                    datetime.datetime.now().strftime("%Y-%m-%d"),
                    TestUserManagement.EMAIL_TEXT,
                )
                + "\n"
            )

    @staticmethod
    @responses.activate
    @pytest.mark.parametrize(
        "email, role, firstname, lastname, username",
        [("new_test@domain.com", "ADMIN", "newfirst", "newlast", "newuser")],
    )
    def test_valid_user_update(
        client, server_config, pytestconfig, email, role, firstname, lastname, username
    ):
        with client:
            runner = CliRunner(mix_stderr=False)
            result = TestUserManagement.register_user(server_config, pytestconfig)
            assert result.exit_code == 0, result.stderr

            result = runner.invoke(
                user_update,
                args=[
                    TestUserManagement.USER_TEXT,
                    TestUserManagement.USER_SWITCH,
                    username,
                    TestUserManagement.EMAIL_SWITCH,
                    email,
                    TestUserManagement.FIRST_NAME_SWITCH,
                    firstname,
                    TestUserManagement.LAST_NAME_SWITCH,
                    lastname,
                    TestUserManagement.ROLE_SWITCH,
                    role,
                ],
            )
            assert result.exit_code == 0
            assert result.stdout == "User test_user updated\n"
            assert not result.stderr_bytes

            # Update with invalid role for the user
            result = runner.invoke(
                user_update, args=[username, TestUserManagement.ROLE_SWITCH, "ADMN",],
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
                result.stdout == f"User {TestUserManagement.USER_TEXT} doesn't exist\n"
            )
            assert not result.stderr_bytes
