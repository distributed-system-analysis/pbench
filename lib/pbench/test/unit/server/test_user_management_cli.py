import datetime

from click.testing import CliRunner
import pytest

import pbench.cli.server.user_management as cli
from pbench.server.database.models.user import User


def create_user():
    user = User(
        username=TestUserManagement.USER_TEXT,
        password=TestUserManagement.PSWD_TEXT,
        first_name=TestUserManagement.FIRST_NAME_TEXT,
        last_name=TestUserManagement.LAST_NAME_TEXT,
        email=TestUserManagement.EMAIL_TEXT,
        registered_on=TestUserManagement.USER_CREATE_TIMESTAMP,
    )
    return user


def mock_valid_list():
    user = create_user()
    return [user]


def mock_valid_delete(**kwargs):
    return


def mock_valid_query(**kwargs):
    return create_user()


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
    USER_CREATE_TIMESTAMP = datetime.datetime.now()

    @staticmethod
    def test_help():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli.user_create, ["--help"])
        assert result.exit_code == 0, result.stderr
        assert str(result.stdout).startswith("Usage:")

    @staticmethod
    def test_valid_user_registration_with_password_input(server_config):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli.user_create,
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
    def test_admin_user_creation(server_config):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli.user_create,
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
    def test_user_creation_with_invalid_role(server_config):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli.user_create,
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
        assert result.exit_code == 2, result.stderr
        assert result.stderr.find("Invalid value for '--role'") > -1

    @staticmethod
    def test_valid_user_delete(monkeypatch, server_config):
        monkeypatch.setattr(User, "delete", mock_valid_delete)
        runner = CliRunner(mix_stderr=False)

        result = runner.invoke(cli.user_delete, args=[TestUserManagement.USER_TEXT])
        assert result.exit_code == 0, result.stderr

    @staticmethod
    def test_invalid_user_delete(server_config):
        runner = CliRunner(mix_stderr=False)
        # Give username that doesn't exists to delete
        result = runner.invoke(cli.user_delete, args=["wrong_username"])
        assert result.exit_code == 1
        assert result.stderr == "User wrong_username does not exist\n"

    @staticmethod
    def test_valid_user_list(monkeypatch, server_config):
        monkeypatch.setattr(User, "query_all", mock_valid_list)
        runner = CliRunner(mix_stderr=False)

        result = runner.invoke(
            cli.user_list,
        )
        assert result.exit_code == 0, result.stderr
        assert (
            result.stdout
            == cli.USER_LIST_HEADER_ROW
            + "\n"
            + cli.USER_LIST_ROW_FORMAT.format(
                TestUserManagement.USER_TEXT,
                TestUserManagement.FIRST_NAME_TEXT,
                TestUserManagement.LAST_NAME_TEXT,
                TestUserManagement.USER_CREATE_TIMESTAMP.strftime("%Y-%m-%d"),
                TestUserManagement.EMAIL_TEXT,
            )
            + "\n"
        )

    @staticmethod
    @pytest.mark.parametrize(
        "switch, value",
        [
            (USER_SWITCH, "new_test"),
            (EMAIL_SWITCH, "new_test@domain.com"),
            (ROLE_SWITCH, "ADMIN"),
            (FIRST_NAME_SWITCH, "newfirst"),
            (LAST_NAME_SWITCH, "newlast"),
            (LAST_NAME_SWITCH, "newuser"),
        ],
    )
    def test_valid_user_update(monkeypatch, server_config, switch, value):
        user = create_user()

        def mock_valid_update(**kwargs):
            for key, value in kwargs.items():
                setattr(user, key, value)
            return

        monkeypatch.setattr(User, "query", mock_valid_query)
        monkeypatch.setattr(user, "update", mock_valid_update)

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli.user_update,
            args=[TestUserManagement.USER_TEXT, switch, value],
        )
        assert result.exit_code == 0, result.stderr
        assert result.stdout == "User test_user updated\n"

    @staticmethod
    def test_invalid_role_update(server_config):
        runner = CliRunner(mix_stderr=False)

        # Update with invalid role for the user
        result = runner.invoke(
            cli.user_update,
            args=["test_user", TestUserManagement.ROLE_SWITCH, "ADMN"],
        )
        assert result.exit_code == 2
        assert result.stderr.find("Invalid value for '--role'") > -1

    @staticmethod
    def test_invalid_user_update(server_config):
        runner = CliRunner(mix_stderr=False)

        # Update with non-existent username
        result = runner.invoke(
            cli.user_update,
            args=[
                TestUserManagement.USER_TEXT,
                TestUserManagement.EMAIL_SWITCH,
                "new_test@domain.com",
            ],
        )
        assert result.exit_code == 1
        assert result.stdout == f"User {TestUserManagement.USER_TEXT} doesn't exist\n"
        assert not result.stderr_bytes
