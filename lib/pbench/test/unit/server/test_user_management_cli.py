from click.testing import CliRunner
import pytest

import pbench.cli.server.user_management as cli
from pbench.server.database.models.users import User


def create_user():
    user = User(
        username=TestUserManagement.USER_TEXT,
        id=TestUserManagement.OIDC_ID_TEXT,
    )
    return user


def mock_valid_list():
    user = create_user()
    return [user]


@pytest.fixture(autouse=True)
def server_config_env(on_disk_server_config, monkeypatch):
    """Provide a pbench server configuration environment variable for all user
    management CLI tests.
    """
    cfg_file = on_disk_server_config["cfg_dir"] / "pbench-server.cfg"
    monkeypatch.setenv("_PBENCH_SERVER_CONFIG", str(cfg_file))


class TestUserManagement:
    USER_TEXT = "test_user"
    OIDC_ID_TEXT = "12345"

    @staticmethod
    def test_help():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(cli.user_list, ["--help"])
        assert result.exit_code == 0, result.stderr
        assert str(result.stdout).startswith("Usage:")

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
