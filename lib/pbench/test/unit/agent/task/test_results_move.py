import datetime
import json
import logging
import re

from click.testing import CliRunner
import pytest
import responses

from pbench.cli.agent.commands.results.move import main
from pbench.test.unit.agent.task.common import MockDatetime

# Template for a mocked "metadata.log" file; the caller needs to
# provide variables for the name, script, config, and date values.
mdlog_tmpl = """[pbench]
name = {name}
script = {script}
config = {config}
date = {date}
rpm-version = 0.00.0-1
iterations = 1, 1

[tools]
hosts = agent.example.com
group = default

[tools/agent.example.com]
sar = --interval=3

[run]
controller = agent.example.com
start_run = YYYY-MM-DDTHH:MM:SS.000000000
end_run = YYYY-MM-DDTHH:MM:SS.000000000

[iterations/1]
iteration_name = 1
user_script = sleep
"""


class TestResultsMove:

    CTRL_SWITCH = "--controller"
    TOKN_SWITCH = "--token"
    ACCESS_SWITCH = "--access"
    DELY_SWITCH = "--delete"
    DELN_SWITCH = "--no-delete"
    XZST_SWITCH = "--xz-single-threaded"
    RELAY_SWITCH = "--relay"
    BRIEF_SWITCH = "--brief"
    SRVR_SWITCH = "--server"
    CTRL_TEXT = "ctrl"
    TOKN_TEXT = "what is a token but 139 characters of gibberish"
    ACCESS_TEXT = "private"
    RELAY_TEXT = "http://relay.example.com"
    SRVR_TEXT = "https://pbench.test.example.com"
    META_SWITCH = "--metadata"
    META_TEXT_FOO = "pbench.sat:FOO"
    META_TEXT_TEST = "pbench.test:TEST"
    URL = "https://pbench.example.com/api/v1"
    ENDPOINT = "/login"

    @staticmethod
    @responses.activate
    def test_help():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert result.stdout.startswith(
            "Usage: pbench-results-move"
        ), f"Unexpected output: {result.stdout!r}"
        assert not result.stderr

    @staticmethod
    @responses.activate
    def test_args():
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsMove.CTRL_SWITCH,
                TestResultsMove.CTRL_TEXT,
                TestResultsMove.TOKN_SWITCH,
                TestResultsMove.TOKN_TEXT,
                TestResultsMove.DELY_SWITCH,
                TestResultsMove.XZST_SWITCH,
                TestResultsMove.SRVR_SWITCH,
                TestResultsMove.SRVR_TEXT,
                TestResultsMove.ACCESS_SWITCH,
                TestResultsMove.ACCESS_TEXT,
            ],
        )
        assert (
            result.exit_code == 0
        ), f"Expected success exit code of 0: exit_code = {result.exit_code:d}, stderr: {result.stderr}, stdout: {result.stdout}"
        assert (
            not result.stderr
        ), f"Unexpected stderr: '{result.stderr}', stdout: '{result.stdout}'"
        assert result.stdout.startswith(
            "Status: total "
        ), f"Unexpected stdout: '{result.stdout}', stderr: '{result.stderr}'"

    @staticmethod
    @responses.activate
    def test_metadata_args():
        """Test metadata with irregular option/value pair"""
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsMove.CTRL_SWITCH,
                TestResultsMove.CTRL_TEXT,
                TestResultsMove.TOKN_SWITCH,
                TestResultsMove.TOKN_TEXT,
                TestResultsMove.DELY_SWITCH,
                TestResultsMove.XZST_SWITCH,
                TestResultsMove.ACCESS_SWITCH,
                TestResultsMove.ACCESS_TEXT,
                TestResultsMove.META_SWITCH,
                TestResultsMove.META_TEXT_TEST,
                TestResultsMove.META_TEXT_FOO,
            ],
        )
        assert (
            result.exit_code == 2
        ), f"Expected exit code of 2: exit_code = {result.exit_code:d}, stderr: {result.stderr}, stdout: {result.stdout}"
        assert "Error: Got unexpected extra argument (pbench.sat:FOO)" in result.stderr

    @staticmethod
    @responses.activate
    def test_server_relay():
        """Test metadata with conflicting server and relay"""
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsMove.CTRL_SWITCH,
                TestResultsMove.CTRL_TEXT,
                TestResultsMove.DELY_SWITCH,
                TestResultsMove.XZST_SWITCH,
                TestResultsMove.SRVR_SWITCH,
                TestResultsMove.SRVR_TEXT,
                TestResultsMove.RELAY_SWITCH,
                TestResultsMove.RELAY_TEXT,
            ],
        )
        assert (
            result.exit_code == 2
        ), f"Expected exit code of 2: exit_code = {result.exit_code:d}, stderr: {result.stderr}, stdout: {result.stdout}"
        assert "Cannot use both relay and Pbench Server destination." in result.stderr

    @staticmethod
    @responses.activate
    def test_multiple_metadata_args():
        """Test metadata with multiple values"""
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestResultsMove.CTRL_SWITCH,
                TestResultsMove.CTRL_TEXT,
                TestResultsMove.TOKN_SWITCH,
                TestResultsMove.TOKN_TEXT,
                TestResultsMove.DELY_SWITCH,
                TestResultsMove.XZST_SWITCH,
                TestResultsMove.ACCESS_SWITCH,
                TestResultsMove.ACCESS_TEXT,
                TestResultsMove.META_SWITCH,
                TestResultsMove.META_TEXT_TEST,
                TestResultsMove.META_SWITCH,
                TestResultsMove.META_TEXT_FOO,
            ],
        )
        assert (
            result.exit_code == 0
        ), f"Expected success exit code of 0: exit_code = {result.exit_code:d}, stderr: {result.stderr}, stdout: {result.stdout}"
        assert (
            not result.stderr
        ), f"Unexpected stderr: '{result.stderr}', stdout: '{result.stdout}'"
        assert result.stdout.startswith(
            "Status: total "
        ), f"Unexpected stdout: '{result.stdout}', stderr: '{result.stderr}'"

    @staticmethod
    @responses.activate
    def test_results_move(monkeypatch, caplog, setup):
        monkeypatch.setenv("_pbench_full_hostname", "localhost")
        monkeypatch.setattr(datetime, "datetime", MockDatetime)

        # In order for a pbench tar ball to be moved/copied to a pbench-server
        # the run directory has to have one file in it, a "metadata.log" file.
        # We make a run directory and populate it with our test specific
        # information.
        pbrun = setup["tmp"] / "var" / "lib" / "pbench-agent"
        script = "pbench-user-benchmark"
        config = "test-results-move"
        date = "YYYY.MM.DDTHH.MM.SS"
        name = f"{script}_{config}_{date}"
        res_dir = pbrun / name
        res_dir.mkdir(parents=True, exist_ok=True)
        mlog = res_dir / "metadata.log"
        mlog.write_text(mdlog_tmpl.format(**locals()))

        caplog.set_level(logging.DEBUG)

        responses.add(
            responses.PUT,
            f"{TestResultsMove.URL}/upload/{name}.tar.xz",
            status=200,
        )

        runner = CliRunner(mix_stderr=False)

        # Test --no-delete
        result = runner.invoke(
            main,
            args=[
                TestResultsMove.CTRL_SWITCH,
                TestResultsMove.CTRL_TEXT,
                TestResultsMove.TOKN_SWITCH,
                TestResultsMove.TOKN_TEXT,
                TestResultsMove.DELN_SWITCH,
            ],
        )
        assert (
            result.exit_code == 0
        ), f"Expected a successful operation, exit_code = {result.exit_code:d}, stderr: {result.stderr}, stdout: {result.stdout}"
        assert (
            result.stdout
            == "Status: total # of result directories considered 1, successfully copied 1, encountered 0 failures\n"
        )
        # This should raise an unexpected exception if it was not created.
        (pbrun / f"{name}.copied").unlink()

        # Test --delete (default) with .running directory.
        (pbrun / name / ".running").mkdir()
        result = runner.invoke(
            main,
            args=[
                TestResultsMove.CTRL_SWITCH,
                TestResultsMove.CTRL_TEXT,
                TestResultsMove.TOKN_SWITCH,
                TestResultsMove.TOKN_TEXT,
            ],
        )
        assert (
            result.exit_code == 0
        ), f"Expected a successful operation, exit_code = {result.exit_code:d}, stderr: {result.stderr}, stdout: {result.stdout}"
        assert (
            result.stdout
            == "Status: total # of result directories considered 1, successfully moved 0, encountered 0 failures\n"
        )
        (pbrun / name / ".running").rmdir()

        # Test --delete (default).
        result = runner.invoke(
            main,
            args=[
                TestResultsMove.CTRL_SWITCH,
                TestResultsMove.CTRL_TEXT,
                TestResultsMove.TOKN_SWITCH,
                TestResultsMove.TOKN_TEXT,
            ],
        )
        assert (
            result.exit_code == 0
        ), f"Expected a successful operation, exit_code = {result.exit_code:d}, stderr: {result.stderr}, stdout: {result.stdout}"
        assert (
            result.stdout
            == "Status: total # of result directories considered 1, successfully moved 1, encountered 0 failures\n"
        )

    @staticmethod
    @responses.activate
    def test_results_move_server(monkeypatch, caplog, setup):
        monkeypatch.setenv("_pbench_full_hostname", "localhost")
        monkeypatch.setattr(datetime, "datetime", MockDatetime)

        # In order for a pbench tar ball to be moved/copied to a pbench-server
        # the run directory has to have one file in it, a "metadata.log" file.
        # We make a run directory and populate it with our test specific
        # information.
        pbrun = setup["tmp"] / "var" / "lib" / "pbench-agent"
        script = "pbench-user-benchmark"
        config = "test-results-move"
        date = "YYYY.MM.DDTHH.MM.SS"
        name = f"{script}_{config}_{date}"
        res_dir = pbrun / name
        res_dir.mkdir(parents=True, exist_ok=True)
        mlog = res_dir / "metadata.log"
        mlog.write_text(mdlog_tmpl.format(**locals()))

        caplog.set_level(logging.DEBUG)

        responses.add(
            responses.PUT,
            f"{TestResultsMove.SRVR_TEXT}/api/v1/upload/{name}.tar.xz",
            status=200,
        )

        runner = CliRunner(mix_stderr=False)

        # Test --no-delete
        result = runner.invoke(
            main,
            args=[
                TestResultsMove.CTRL_SWITCH,
                TestResultsMove.CTRL_TEXT,
                TestResultsMove.TOKN_SWITCH,
                TestResultsMove.TOKN_TEXT,
                TestResultsMove.DELN_SWITCH,
                TestResultsMove.SRVR_SWITCH,
                TestResultsMove.SRVR_TEXT,
            ],
        )
        assert (
            result.exit_code == 0
        ), f"Expected a successful operation, exit_code = {result.exit_code:d}, stderr: {result.stderr}, stdout: {result.stdout}"
        assert (
            result.stdout
            == "Status: total # of result directories considered 1, successfully copied 1, encountered 0 failures\n"
        )
        # This should raise an unexpected exception if it was not created.
        (pbrun / f"{name}.copied").unlink()

    @staticmethod
    @responses.activate
    @pytest.mark.parametrize("brief", (True, False))
    def test_results_move_relay(monkeypatch, caplog, setup, brief):
        monkeypatch.setenv("_pbench_full_hostname", "localhost")
        monkeypatch.setattr(datetime, "datetime", MockDatetime)

        # In order for a pbench tar ball to be moved/copied to a pbench-server
        # the run directory has to have one file in it, a "metadata.log" file.
        # We make a run directory and populate it with our test specific
        # information.
        pbrun = setup["tmp"] / "var" / "lib" / "pbench-agent"
        script = "pbench-user-benchmark"
        config = "test-results-move"
        date = "YYYY.MM.DDTHH.MM.SS"
        name = f"{script}_{config}_{date}"
        res_dir = pbrun / name
        res_dir.mkdir(parents=True, exist_ok=True)
        mlog = res_dir / "metadata.log"
        mlog.write_text(mdlog_tmpl.format(**locals()))

        caplog.set_level(logging.DEBUG)

        responses.add(
            responses.PUT, re.compile(f"{TestResultsMove.RELAY_TEXT}/[a-z0-9]+")
        )

        runner = CliRunner(mix_stderr=False)

        arg_list = [
            TestResultsMove.CTRL_SWITCH,
            TestResultsMove.CTRL_TEXT,
            TestResultsMove.DELN_SWITCH,
            TestResultsMove.RELAY_SWITCH,
            TestResultsMove.RELAY_TEXT,
        ]

        if brief:
            arg_list.append(TestResultsMove.BRIEF_SWITCH)

        # Test --no-delete
        result = runner.invoke(
            main,
            args=arg_list,
        )

        # We expect two PUT calls using the relay base URI: first the tarball
        # itself, and then a JSON manifest file. The manifest JSON must contain
        # a "uri" field with a value matching the tarball URI, and a "name"
        # field identifying the original tarball name.
        assert len(responses.calls) == 2
        calls = list(responses.calls)
        manifest = json.load(calls[1].request.body)
        assert manifest["uri"] == calls[0].request.url
        assert manifest["name"] == f"{name}.tar.xz"
        assert (
            result.exit_code == 0
        ), f"Expected a successful operation, exit_code = {result.exit_code:d}, stderr: {result.stderr}, stdout: {result.stdout}"
        pattern = r"http://relay.example.com/[a-z0-9]+\n"
        if not brief:
            pattern = (
                "RELAY pbench-user-benchmark_test-results-move_YYYY.MM.DDTHH.MM.SS.tar.xz: "
                + pattern
                + "Status: total # of result directories considered 1, successfully copied 1, encountered 0 failures\n"
            )
        assert re.match(pattern, result.stdout)
        # This should raise an unexpected exception if it was not created.
        (pbrun / f"{name}.copied").unlink()
