from click.testing import CliRunner
import pytest

import pbench.cli.server.user_management as cli
from pbench.server.database.models.users import User


def create_user():
    user = User(
        username=TestUserManagement.USER_TEXT,
        oidc_id=TestUserManagement.OIDC_ID_TEXT,
    )
    return user


def mock_valid_list():
    user = create_user()
    return [user]


def mock_valid_delete(obj):
    return


def mock_valid_query(**kwargs):
    return create_user()


@pytest.fixture(autouse=True)
def server_config_env(on_disk_server_config, monkeypatch):
    """Provide a pbench server configuration environment variable for all user
    management CLI tests.
    """
    cfg_file = on_disk_server_config["cfg_dir"] / "pbench-server.cfg"
    monkeypatch.setenv("_PBENCH_SERVER_CONFIG", str(cfg_file))


class TestUserManagement:
    USER_SWITCH = "--username"
    OIDC_SWITCH = "--oidc-id"
    ROLE_SWITCH = "--role"
    USER_TEXT = "test_user"
    OIDC_ID_TEXT = "12345"
    EMAIL_TEXT = "test@domain.com"

    @staticmethod
    def test_help():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli.user_create, ["--help"])
        assert result.exit_code == 0, result.stderr
        assert str(result.stdout).startswith("Usage:")

    @staticmethod
    def test_valid_user_registration(server_config):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli.user_create,
            args=[
                TestUserManagement.USER_SWITCH,
                TestUserManagement.USER_TEXT,
                TestUserManagement.OIDC_SWITCH,
                TestUserManagement.OIDC_ID_TEXT,
            ],
        )
        assert result.exit_code == 0, result.stderr
        assert result.stdout == "User test_user registered\n"

    @staticmethod
    def test_admin_user_creation(server_config):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            cli.user_create,
            args=[
                TestUserManagement.USER_SWITCH,
                TestUserManagement.USER_TEXT,
                TestUserManagement.OIDC_SWITCH,
                TestUserManagement.OIDC_ID_TEXT,
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
                TestUserManagement.OIDC_SWITCH,
                TestUserManagement.OIDC_ID_TEXT,
                TestUserManagement.ROLE_SWITCH,
                "ADMN",
            ],
        )
        assert result.exit_code == 2, result.stderr
        assert result.stderr.find("Invalid value for '--role'") > -1

    @staticmethod
    def test_valid_user_delete(monkeypatch, server_config):
        monkeypatch.setattr(User, "query", mock_valid_query)
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
                TestUserManagement.USER_TEXT, TestUserManagement.OIDC_ID_TEXT
            )
            + "\n"
        )

    @staticmethod
    @pytest.mark.parametrize(
        "switch, value",
        [
            (ROLE_SWITCH, "ADMIN"),
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
                TestUserManagement.ROLE_SWITCH,
                "ADMIN",
            ],
        )
        assert result.exit_code == 1
        assert result.stdout == f"User {TestUserManagement.USER_TEXT} doesn't exist\n"
        assert not result.stderr_bytes
