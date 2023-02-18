import datetime
import logging

from click.testing import CliRunner
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


class TestMoveResults:

    CTRL_SWITCH = "--controller"
    TOKN_SWITCH = "--token"
    ACCESS_SWITCH = "--access"
    DELY_SWITCH = "--delete"
    DELN_SWITCH = "--no-delete"
    XZST_SWITCH = "--xz-single-threaded"
    SWSR_SWITCH = "--show-server"
    CTRL_TEXT = "ctrl"
    TOKN_TEXT = "what is a token but 139 characters of gibberish"
    ACCESS_TEXT = "private"
    SWSR_TEXT = None
    META_SWITCH = "--metadata"
    META_TEXT_FOO = "pbench.sat:FOO"
    META_TEXT_TEST = "pbench.test:TEST"
    URL = "http://pbench.example.com/api/v1"
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
                TestMoveResults.CTRL_SWITCH,
                TestMoveResults.CTRL_TEXT,
                TestMoveResults.TOKN_SWITCH,
                TestMoveResults.TOKN_TEXT,
                TestMoveResults.DELY_SWITCH,
                TestMoveResults.XZST_SWITCH,
                TestMoveResults.SWSR_SWITCH,
                TestMoveResults.SWSR_TEXT,
                TestMoveResults.ACCESS_SWITCH,
                TestMoveResults.ACCESS_TEXT,
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
                TestMoveResults.CTRL_SWITCH,
                TestMoveResults.CTRL_TEXT,
                TestMoveResults.TOKN_SWITCH,
                TestMoveResults.TOKN_TEXT,
                TestMoveResults.DELY_SWITCH,
                TestMoveResults.XZST_SWITCH,
                TestMoveResults.SWSR_SWITCH,
                TestMoveResults.SWSR_TEXT,
                TestMoveResults.ACCESS_SWITCH,
                TestMoveResults.ACCESS_TEXT,
                TestMoveResults.META_SWITCH,
                TestMoveResults.META_TEXT_TEST,
                TestMoveResults.META_TEXT_FOO,
            ],
        )
        assert (
            result.exit_code == 2
        ), f"Expected exit code of 2: exit_code = {result.exit_code:d}, stderr: {result.stderr}, stdout: {result.stdout}"
        assert "Error: Got unexpected extra argument (pbench.sat:FOO)" in result.stderr

    @staticmethod
    @responses.activate
    def test_multiple_metadata_args():
        """Test metadata with multiple values"""
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            main,
            args=[
                TestMoveResults.CTRL_SWITCH,
                TestMoveResults.CTRL_TEXT,
                TestMoveResults.TOKN_SWITCH,
                TestMoveResults.TOKN_TEXT,
                TestMoveResults.DELY_SWITCH,
                TestMoveResults.XZST_SWITCH,
                TestMoveResults.SWSR_SWITCH,
                TestMoveResults.SWSR_TEXT,
                TestMoveResults.ACCESS_SWITCH,
                TestMoveResults.ACCESS_TEXT,
                TestMoveResults.META_SWITCH,
                TestMoveResults.META_TEXT_TEST,
                TestMoveResults.META_SWITCH,
                TestMoveResults.META_TEXT_FOO,
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
            responses.GET,
            "http://pbench.example.com/api/v1/host_info",
            status=200,
            body="pbench@pbench-server:/srv/pbench/pbench-move-results-receive/fs-version-002",
        )
        responses.add(
            responses.PUT,
            f"http://pbench.example.com/api/v1/upload/{script}_{config}_{date}.tar.xz",
            status=200,
        )

        runner = CliRunner(mix_stderr=False)

        # Test --no-delete
        result = runner.invoke(
            main,
            args=[
                TestMoveResults.CTRL_SWITCH,
                TestMoveResults.CTRL_TEXT,
                TestMoveResults.TOKN_SWITCH,
                TestMoveResults.TOKN_TEXT,
                TestMoveResults.DELN_SWITCH,
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
                TestMoveResults.CTRL_SWITCH,
                TestMoveResults.CTRL_TEXT,
                TestMoveResults.TOKN_SWITCH,
                TestMoveResults.TOKN_TEXT,
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
                TestMoveResults.CTRL_SWITCH,
                TestMoveResults.CTRL_TEXT,
                TestMoveResults.TOKN_SWITCH,
                TestMoveResults.TOKN_TEXT,
            ],
        )
        assert (
            result.exit_code == 0
        ), f"Expected a successful operation, exit_code = {result.exit_code:d}, stderr: {result.stderr}, stdout: {result.stdout}"
        assert (
            result.stdout
            == "Status: total # of result directories considered 1, successfully moved 1, encountered 0 failures\n"
        )
