import datetime
import logging
import os
from pathlib import Path

import responses
from click.testing import CliRunner

from pbench.cli.agent.commands.results import move
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
    DELY_SWITCH = "--delete"
    DELN_SWITCH = "--no-delete"
    XZST_SWITCH = "--xz-single-threaded"
    SWSR_SWITCH = "--show-server"
    TOKN_PROMPT = "Token: "
    CTRL_TEXT = "ctrl"
    TOKN_TEXT = "what is a token but 139 characters of gibberish"
    SWSR_TEXT = None
    URL = "http://pbench.example.com/api/v1"
    ENDPOINT = "/login"

    @staticmethod
    @responses.activate
    def test_help(pytestconfig):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(move.main, ["--help"])
        assert result.exit_code == 0
        assert str(result.stdout).startswith("Usage:")
        assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_args(valid_config, pytestconfig):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            move.main,
            args=[
                TestMoveResults.CTRL_SWITCH,
                TestMoveResults.CTRL_TEXT,
                TestMoveResults.TOKN_SWITCH,
                TestMoveResults.TOKN_TEXT,
                TestMoveResults.DELY_SWITCH,
                TestMoveResults.XZST_SWITCH,
                TestMoveResults.SWSR_SWITCH,
                TestMoveResults.SWSR_TEXT,
            ],
        )
        assert result.exit_code == 0, f"Expected success exit code of 0: {result!r}"
        assert (
            not result.stderr_bytes
        ), f"Unexpected stderr bytes: '{result.stderr_bytes}', stdout: '{result.stdout_bytes}'"
        assert result.stdout_bytes.startswith(
            b"Status: total "
        ), f"Unexpected stdout bytes: '{result.stdout_bytes}', stderr: '{result.stderr_bytes}'"

    @staticmethod
    @responses.activate
    def test_results_move(monkeypatch, caplog, pytestconfig):
        monkeypatch.setenv("_pbench_full_hostname", "localhost")
        monkeypatch.setattr(datetime, "datetime", MockDatetime)

        ctx = {"args": {"config": os.environ["_PBENCH_AGENT_CONFIG"]}}

        # In order for a pbench tar ball to be moved/copied to a pbench-server
        # the run directory has to have one file in it, a "metadata.log" file.
        # We make a run directory and populate it with our test specific
        # information.
        TMP = pytestconfig.cache.get("TMP", None)
        pbrun = Path(TMP) / "var" / "lib" / "pbench-agent"
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
            move.main,
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
        ), f"Expected a successful operation, exit_code == {result.exit_code:d}"
        assert (
            result.stdout
            == "Status: total # of result directories considered 1, successfully copied 1, encountered 0 failures\n"
        )
        # This should raise an unexpected exception if it was not created.
        (pbrun / f"{name}.copied").unlink()

        # Test --delete (default) with .running directory.
        (pbrun / name / ".running").mkdir()
        result = runner.invoke(
            move.main,
            args=[
                TestMoveResults.CTRL_SWITCH,
                TestMoveResults.CTRL_TEXT,
                TestMoveResults.TOKN_SWITCH,
                TestMoveResults.TOKN_TEXT,
            ],
        )
        assert (
            result.exit_code == 1
        ), f"Expected an unsuccessful operation, exit_code == {result.exit_code:d}"
        assert (
            result.stdout
            == "Status: total # of result directories considered 1, successfully moved 0, encountered 1 failures\n"
        )
        (pbrun / name / ".running").rmdir()

        # Test --delete (default).
        result = runner.invoke(
            move.main,
            args=[
                TestMoveResults.CTRL_SWITCH,
                TestMoveResults.CTRL_TEXT,
                TestMoveResults.TOKN_SWITCH,
                TestMoveResults.TOKN_TEXT,
            ],
        )
        assert (
            result.exit_code == 0
        ), f"Expected a successful operation, exit_code == {result.exit_code:d}"
        assert (
            result.stdout
            == "Status: total # of result directories considered 1, successfully moved 1, encountered 0 failures\n"
        )
