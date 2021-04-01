from click.testing import CliRunner
import responses

from pbench.cli.server import user_create


class TestCreateUser:
    USER_SWITCH = "--username"
    PSWD_SWITCH = "--password"
    PSWD_PROMPT = "Password: "
    EMAIL_SWITCH = "--email"
    FIRST_NAME_SWITCH = "--first-name"
    LAST_NAME_SWITCH = "--last-name"
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
        result = runner.invoke(user_create.main, ["--help"])
        assert result.exit_code == 0
        assert str(result.stdout).startswith("Usage:")
        assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_args(server_config, pytestconfig):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            user_create.main,
            args=[
                TestCreateUser.USER_SWITCH,
                TestCreateUser.USER_TEXT,
                TestCreateUser.PSWD_SWITCH,
                TestCreateUser.PSWD_TEXT,
                TestCreateUser.EMAIL_SWITCH,
                TestCreateUser.EMAIL_TEXT,
                TestCreateUser.FIRST_NAME_SWITCH,
                TestCreateUser.FIRST_NAME_TEXT,
                TestCreateUser.LAST_NAME_SWITCH,
                TestCreateUser.LAST_NAME_TEXT,
            ],
        )
        assert result.stdout_bytes == b"User test_user registered\n"
        assert result.exit_code == 0
        assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_valid_user_registration(server_config, pytestconfig):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            user_create.main,
            args=[
                TestCreateUser.USER_SWITCH,
                TestCreateUser.USER_TEXT,
                TestCreateUser.EMAIL_SWITCH,
                TestCreateUser.EMAIL_TEXT,
                TestCreateUser.FIRST_NAME_SWITCH,
                TestCreateUser.FIRST_NAME_TEXT,
                TestCreateUser.LAST_NAME_SWITCH,
                TestCreateUser.LAST_NAME_TEXT,
            ],
            input=f"{TestCreateUser.PSWD_TEXT}\n",
        )
        assert result.exit_code == 0
        assert (
            result.stdout
            == f"{TestCreateUser.PSWD_PROMPT}\n" + "User test_user registered\n"
        )
        assert not result.stderr_bytes
