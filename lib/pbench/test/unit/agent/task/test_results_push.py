from http import HTTPStatus
import os
import re
from typing import Dict, Optional, Union

from click.testing import CliRunner
import pytest
import requests
import responses

from pbench.cli.agent.commands.results.push import main
from pbench.test.unit.agent.task.common import bad_tarball, tarball


class TestResultsPush:

    TOKN_SWITCH = "--token"
    TOKN_TEXT = "what is a token but 139 characters of gibberish"
    ACCESS_SWITCH = "--access"
    ACCESS_TEXT = "public"
    ACCESS_WRONG_TEXT = "public/private"
    META_SWITCH = "--metadata"
    META_TEXT_FOO = "pbench.sat:FOO"
    META_TEXT_TEST = "pbench.test:TEST"
    RELAY_SWITCH = "--relay"
    BRIEF_SWITCH = "--brief"
    SRVR_SWITCH = "--server"
    RELAY_TEXT = "http://relay.example.com"
    SRVR_TEXT = "https://pbench.test.example.com"
    URL = "https://pbench.example.com/api/v1"

    @staticmethod
    def server_mock(
        status_code: HTTPStatus = HTTPStatus.CREATED,
        message: Optional[Union[str, Dict, Exception]] = None,
    ):
        parms = {}
        if status_code:
            parms["status"] = status_code

        if isinstance(message, dict):
            parms["json"] = message
        elif isinstance(message, (str, Exception)):
            parms["body"] = message

        responses.add(
            responses.PUT,
            f"{TestResultsPush.URL}/upload/{os.path.basename(tarball)}",
            **parms,
        )

    @staticmethod
    def relay_mock(
        status_code: HTTPStatus = HTTPStatus.CREATED,
        error: Optional[Exception] = None,
    ):
        parms = {}
        if status_code:
            parms["status"] = status_code

        if error:
            parms["body"] = error

        responses.add(
            responses.PUT,
            re.compile(f"{TestResultsPush.RELAY_TEXT}/[a-f0-9]+"),
            **parms,
        )

    @staticmethod
    @responses.activate
    def test_help():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0, result.stderr
        assert result.stdout.startswith("Usage: pbench-results-push")
        assert not result.stderr

    @staticmethod
    @responses.activate
    def test_missing_arg():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsPush.TOKN_SWITCH,
                TestResultsPush.TOKN_TEXT,
            ],
        )
        assert result.exit_code == 2
        assert "Missing argument" in result.stderr

    @staticmethod
    @responses.activate
    def test_bad_arg():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsPush.TOKN_SWITCH,
                TestResultsPush.TOKN_TEXT,
                bad_tarball,
            ],
        )
        assert result.exit_code == 2
        assert (
            "Invalid value for 'RESULT_TB_NAME': "
            "File 'nothing.tar.xz' does not exist." in result.stderr
        )

    @staticmethod
    @responses.activate
    def test_server_and_relay():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsPush.SRVR_SWITCH,
                TestResultsPush.SRVR_TEXT,
                TestResultsPush.TOKN_SWITCH,
                TestResultsPush.TOKN_TEXT,
                TestResultsPush.RELAY_SWITCH,
                TestResultsPush.RELAY_TEXT,
                tarball,
            ],
        )
        assert result.exit_code == 2
        assert "Cannot use both relay and Pbench Server destination." in result.stderr

    @staticmethod
    @responses.activate
    @pytest.mark.parametrize("brief", (True, False))
    def test_relay(brief):
        TestResultsPush.relay_mock()
        runner = CliRunner(mix_stderr=False)
        arg_list = [
            TestResultsPush.RELAY_SWITCH,
            TestResultsPush.RELAY_TEXT,
            tarball,
        ]
        if brief:
            arg_list.append(TestResultsPush.BRIEF_SWITCH)
        result = runner.invoke(main, args=arg_list)
        assert result.exit_code == 0
        pattern = (
            "RELAY log.tar.xz: " if not brief else ""
        ) + r"http://relay.example.com/[a-z0-9]+\n"
        assert re.match(pattern, result.stdout)

    @staticmethod
    @responses.activate
    def test_meta_args():
        """Test operation when irregular arguments and options are specified"""

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsPush.TOKN_SWITCH,
                TestResultsPush.TOKN_TEXT,
                TestResultsPush.ACCESS_SWITCH,
                TestResultsPush.ACCESS_TEXT,
                TestResultsPush.META_SWITCH,
                TestResultsPush.META_TEXT_TEST,
                TestResultsPush.META_TEXT_FOO,
                tarball,
            ],
        )
        assert result.exit_code == 2
        assert (
            "Invalid value for 'RESULT_TB_NAME': "
            "File 'pbench.sat:FOO' does not exist." in result.stderr
        )

    @staticmethod
    @responses.activate
    def test_extra_arg():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsPush.TOKN_SWITCH,
                TestResultsPush.TOKN_TEXT,
                tarball,
                "extra-arg",
            ],
        )
        assert result.exit_code == 2
        assert "unexpected extra argument" in result.stderr

    @staticmethod
    @responses.activate
    def test_multiple_meta_args_single_option():
        """Test normal operation when all arguments and options are specified"""

        TestResultsPush.server_mock()
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsPush.TOKN_SWITCH,
                TestResultsPush.TOKN_TEXT,
                TestResultsPush.ACCESS_SWITCH,
                TestResultsPush.ACCESS_TEXT,
                TestResultsPush.META_SWITCH,
                TestResultsPush.META_TEXT_TEST + "," + TestResultsPush.META_TEXT_FOO,
                tarball,
            ],
        )
        assert result.exit_code == 0, result.stderr
        assert result.stdout == ""

    @staticmethod
    @responses.activate
    def test_multiple_meta_args():
        """Test normal operation when all arguments and options are specified"""

        TestResultsPush.server_mock()
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsPush.TOKN_SWITCH,
                TestResultsPush.TOKN_TEXT,
                TestResultsPush.ACCESS_SWITCH,
                TestResultsPush.ACCESS_TEXT,
                TestResultsPush.META_SWITCH,
                TestResultsPush.META_TEXT_TEST,
                TestResultsPush.META_SWITCH,
                TestResultsPush.META_TEXT_FOO,
                tarball,
            ],
        )
        assert result.exit_code == 0, result.stderr
        assert result.stderr == ""

    @staticmethod
    @responses.activate
    def test_token_omitted():
        """Test error when the token option is omitted"""

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, args=[tarball])
        assert result.exit_code == 2, result.stderr
        assert "Error: Missing option '--token'" in str(result.stderr)

    @staticmethod
    @responses.activate
    def test_token_envar(monkeypatch):
        """Test normal operation with the token in an environment variable"""

        monkeypatch.setenv("PBENCH_ACCESS_TOKEN", TestResultsPush.TOKN_TEXT)
        TestResultsPush.server_mock()
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, args=[tarball])
        assert result.exit_code == 0, result.stderr
        assert result.stdout == ""

    @staticmethod
    @responses.activate
    def test_access_error(monkeypatch):
        """Test error in access value"""

        monkeypatch.setenv("PBENCH_ACCESS_TOKEN", TestResultsPush.TOKN_TEXT)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                tarball,
                TestResultsPush.ACCESS_SWITCH,
                TestResultsPush.ACCESS_WRONG_TEXT,
            ],
        )
        assert result.exit_code == 2, result.stderr
        assert "Error: Invalid value for '-a' / '--access': 'public/private'" in str(
            result.stderr
        )

    @staticmethod
    @responses.activate
    @pytest.mark.parametrize(
        "status_code,message,exit_code",
        (
            (HTTPStatus.CREATED, None, 0),
            (HTTPStatus.OK, {"message": "Dup"}, 0),
            (HTTPStatus.OK, "Dup", 0),
            (HTTPStatus.NO_CONTENT, {"message": "No content"}, 0),
            (HTTPStatus.NO_CONTENT, "No content", 0),
            (
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"message": "Request Entity Too Large"},
                1,
            ),
            (HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request Entity Too Large", 1),
            (HTTPStatus.NOT_FOUND, {"message": "Not Found"}, 1),
            (HTTPStatus.NOT_FOUND, "Not Found", 1),
            (None, requests.exceptions.ConnectionError("Oops"), 1),
        ),
    )
    def test_push_status(status_code, message, exit_code):
        """Test normal operation when all arguments and options are specified"""

        TestResultsPush.server_mock(status_code, message)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsPush.TOKN_SWITCH,
                TestResultsPush.TOKN_TEXT,
                TestResultsPush.ACCESS_SWITCH,
                TestResultsPush.ACCESS_TEXT,
                TestResultsPush.META_SWITCH,
                TestResultsPush.META_TEXT_TEST + "," + TestResultsPush.META_TEXT_FOO,
                tarball,
            ],
        )

        assert result.exit_code == exit_code, result.stderr
        assert result.stdout == ""

        if not message:
            err_msg = ""
        elif isinstance(message, dict):
            err_msg = message["message"]
        elif isinstance(message, str):
            err_msg = message
        elif isinstance(message, Exception):
            err_msg = str(message)
        else:
            assert False, "message must be dict, string, Exception or None"

        if status_code and status_code >= 400:
            err_msg = f"HTTP Error status: {status_code.value}, message: {err_msg}"
        assert err_msg in result.stderr
