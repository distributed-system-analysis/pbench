from click.testing import CliRunner
from http import HTTPStatus
import requests
import responses

from pbench.cli.agent.commands import generate_token


class TestGenerateToken:

    USER_SWITCH = "--username"
    PSWD_SWITCH = "--password"
    USER_PROMPT = "Username: "
    PSWD_PROMPT = "Password: "
    USER_TEXT = "test_user"
    PSWD_TEXT = "password"
    TOKEN_TEXT = "what is a token but 139 characters of gibberish"
    URL = "http://pbench.example.com/api/v1"
    ENDPOINT = "/login"

    @staticmethod
    def add_success_mock_response():
        responses.add(
            responses.POST,
            TestGenerateToken.URL + TestGenerateToken.ENDPOINT,
            status=HTTPStatus.OK,
            json={"auth_token": TestGenerateToken.TOKEN_TEXT},
        )

    @staticmethod
    def add_badlogin_mock_response():
        responses.add(
            responses.POST,
            TestGenerateToken.URL + TestGenerateToken.ENDPOINT,
            status=HTTPStatus.FORBIDDEN,
            json={"message": "Bad login"},
        )

    @staticmethod
    def add_connectionerr_mock_response():
        responses.add(
            responses.POST,
            TestGenerateToken.URL + TestGenerateToken.ENDPOINT,
            body=requests.exceptions.ConnectionError(
                "<urllib3.connection.HTTPConnection object at 0x1080854c0>: "
                "Failed to establish a new connection: [Errno 8] "
                "nodename nor servname provided, or not known"
            ),
        )

    @staticmethod
    @responses.activate
    def test_help(pytestconfig):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(generate_token.main, ["--help"])
        assert result.exit_code == 0
        assert str(result.stdout).startswith("Usage:")
        assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_args_both(valid_config, pytestconfig):
        TestGenerateToken.add_success_mock_response()
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            generate_token.main,
            args=[
                TestGenerateToken.USER_SWITCH,
                TestGenerateToken.USER_TEXT,
                TestGenerateToken.PSWD_SWITCH,
                TestGenerateToken.PSWD_TEXT,
            ],
        )
        assert result.exit_code == 0
        assert result.stdout == f"{TestGenerateToken.TOKEN_TEXT}\n"
        assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_args_username(valid_config, pytestconfig):
        TestGenerateToken.add_success_mock_response()
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            generate_token.main,
            args=[TestGenerateToken.USER_SWITCH, TestGenerateToken.USER_TEXT],
            input=f"{TestGenerateToken.PSWD_TEXT}\n",
        )
        assert result.exit_code == 0
        assert (
            result.stdout
            == f"{TestGenerateToken.PSWD_PROMPT}\n"
            + f"{TestGenerateToken.TOKEN_TEXT}\n"
        )
        assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_args_password(valid_config, pytestconfig):
        TestGenerateToken.add_success_mock_response()
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            generate_token.main,
            args=[TestGenerateToken.PSWD_SWITCH, TestGenerateToken.PSWD_TEXT],
            input=f"{TestGenerateToken.USER_TEXT}\n",
        )
        assert result.exit_code == 0
        assert (
            result.stdout
            == f"{TestGenerateToken.USER_PROMPT}{TestGenerateToken.USER_TEXT}\n"
            + f"{TestGenerateToken.TOKEN_TEXT}\n"
        )
        assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_args_none(valid_config, pytestconfig):
        TestGenerateToken.add_success_mock_response()
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            generate_token.main,
            args=[],
            input=f"{TestGenerateToken.USER_TEXT}\n{TestGenerateToken.PSWD_TEXT}\n",
        )
        assert result.exit_code == 0
        assert (
            result.stdout
            == f"{TestGenerateToken.USER_PROMPT}{TestGenerateToken.USER_TEXT}\n"
            + f"{TestGenerateToken.PSWD_PROMPT}\n"
            + f"{TestGenerateToken.TOKEN_TEXT}\n"
        )
        assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_bad_login(valid_config, pytestconfig):
        TestGenerateToken.add_badlogin_mock_response()
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            generate_token.main,
            args=[
                TestGenerateToken.USER_SWITCH,
                TestGenerateToken.USER_TEXT,
                TestGenerateToken.PSWD_SWITCH,
                TestGenerateToken.PSWD_TEXT,
            ],
        )
        assert result.exit_code == 1
        assert not result.stdout
        assert result.stderr == "Bad login\n"

    @staticmethod
    @responses.activate
    def test_connection_failed(valid_config, pytestconfig):

        TestGenerateToken.add_connectionerr_mock_response()
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            generate_token.main,
            args=[
                TestGenerateToken.USER_SWITCH,
                TestGenerateToken.USER_TEXT,
                TestGenerateToken.PSWD_SWITCH,
                TestGenerateToken.PSWD_TEXT,
            ],
        )
        assert result.exit_code == 1
        assert not result.stdout
        assert -1 != str(result.stderr).find(
            "Cannot connect to 'http://pbench.example.com/api/v1/login'"
        )
