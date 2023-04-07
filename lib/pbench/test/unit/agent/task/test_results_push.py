from http import HTTPStatus
import logging
import os
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
    URL = "http://pbench.example.com/api/v1"

    @staticmethod
    def add_http_mock_response(
        status_code: HTTPStatus = None, message: Optional[Union[str, Dict]] = None
    ):
        if status_code:
            if message is None:
                responses.add(
                    responses.PUT,
                    f"{TestResultsPush.URL}/upload/{os.path.basename(tarball)}",
                    status=status_code,
                )
            elif isinstance(message, dict):
                responses.add(
                    responses.PUT,
                    f"{TestResultsPush.URL}/upload/{os.path.basename(tarball)}",
                    status=status_code,
                    json=message,
                )
        else:
            responses.add(
                responses.PUT,
                f"{TestResultsPush.URL}/upload/{os.path.basename(tarball)}",
            )

    @staticmethod
    def add_connectionerr_mock_response():
        responses.add(
            responses.PUT,
            f"{TestResultsPush.URL}/upload/{os.path.basename(tarball)}",
            body=requests.exceptions.ConnectionError(
                "<urllib3.connection.HTTPConnection object at 0x1080854c0>: "
                "Failed to establish a new connection: [Errno 8] "
                "nodename nor servname provided, or not known"
            ),
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
        assert result.stderr.find("Missing argument") > -1

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
        assert result.stderr.find(
            "Invalid value for 'RESULT_TB_NAME': "
            "File 'nothing.tar.xz' does not exist."
        )

    @staticmethod
    @responses.activate
    def test_meta_args():
        """Test operation when irregular arguments and options are specified"""

        TestResultsPush.add_http_mock_response()
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
        assert result.stderr.find("unexpected extra argument") > -1

    @staticmethod
    @responses.activate
    def test_multiple_meta_args_single_option():
        """Test normal operation when all arguments and options are specified"""

        TestResultsPush.add_http_mock_response()
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

        TestResultsPush.add_http_mock_response()
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
        assert result.stdout == ""

    @staticmethod
    @responses.activate
    @pytest.mark.parametrize(
        "status_code,message,exit_code",
        (
            (HTTPStatus.CREATED, None, 0),
            (HTTPStatus.OK, {"message": "Dup"}, 0),
            (HTTPStatus.NO_CONTENT, {"message": "No content"}, 0),
            (
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"message": "Request Entity Too Large"},
                1,
            ),
            (HTTPStatus.NOT_FOUND, {"message": "Not Found"}, 1),
        ),
    )
    def test_push_status(status_code, message, exit_code):
        """Test normal operation when all arguments and options are specified"""

        TestResultsPush.add_http_mock_response(status_code, message)
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
        assert result.stderr.strip() == "" if not message else message["message"]

    @staticmethod
    @responses.activate
    def test_error_too_large_tarball():
        """Test normal operation when all arguments and options are specified"""

        TestResultsPush.add_http_mock_response(
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            message={"message": "Request Entity Too Large"},
        )
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
        assert result.exit_code == 1, result.stderr
        assert (
            result.stderr
            == "HTTP Error status: 413, message: Request Entity Too Large\n"
        )

    @staticmethod
    @responses.activate
    def test_token_omitted():
        """Test error when the token option is omitted"""

        TestResultsPush.add_http_mock_response()
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, args=[tarball])
        assert result.exit_code == 2, result.stderr
        assert "Missing option '--token'" in str(result.stderr)

    @staticmethod
    @responses.activate
    def test_token_envar(monkeypatch, caplog):
        """Test normal operation with the token in an environment variable"""

        monkeypatch.setenv("PBENCH_ACCESS_TOKEN", TestResultsPush.TOKN_TEXT)
        TestResultsPush.add_http_mock_response()
        caplog.set_level(logging.DEBUG)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, args=[tarball])
        assert result.exit_code == 0, result.stderr
        assert result.stdout == ""

    @staticmethod
    @responses.activate
    def test_access_error(monkeypatch, caplog):
        """Test error in access value"""

        monkeypatch.setenv("PBENCH_ACCESS_TOKEN", TestResultsPush.TOKN_TEXT)
        TestResultsPush.add_http_mock_response()
        caplog.set_level(logging.DEBUG)
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
    def test_connection_error(monkeypatch, caplog):
        """Test handling of connection errors"""

        monkeypatch.setenv("PBENCH_ACCESS_TOKEN", TestResultsPush.TOKN_TEXT)
        TestResultsPush.add_connectionerr_mock_response()
        caplog.set_level(logging.DEBUG)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, args=[tarball])
        assert result.exit_code == 1
        assert str(result.stderr).startswith("Cannot connect to")

    @staticmethod
    @responses.activate
    def test_http_error(monkeypatch, caplog):
        """Test handling of 404 errors"""

        monkeypatch.setenv("PBENCH_ACCESS_TOKEN", TestResultsPush.TOKN_TEXT)
        TestResultsPush.add_http_mock_response(
            HTTPStatus.NOT_FOUND, message={"message": "Not Found"}
        )
        caplog.set_level(logging.DEBUG)
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, args=[tarball])
        assert result.exit_code == 1
        assert (
            str(result.stderr).find("Not Found") > -1
        ), f"stderr: {result.stderr!r}; stdout: {result.stdout!r}"
