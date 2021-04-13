import datetime
import logging
import os
from pathlib import Path

import responses
from click.testing import CliRunner

from pbench.cli.agent.commands import results
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
    USER_SWITCH = "--user"
    TOKN_SWITCH = "--token"
    PRFX_SWITCH = "--prefix"
    XZST_SWITCH = "--xz-single-threaded"
    SWSR_SWITCH = "--show-server"
    TOKN_PROMPT = "Token: "
    CTRL_TEXT = "ctrl"
    USER_TEXT = None
    TOKN_TEXT = "what is a token but 139 characters of gibberish"
    PRFX_TEXT = None
    XZST_TEXT = None
    SWSR_TEXT = None
    URL = "http://pbench.example.com/api/v1"
    ENDPOINT = "/login"

    @staticmethod
    @responses.activate
    def test_help(pytestconfig):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(results.pmr, ["--help"])
        assert result.exit_code == 0
        assert str(result.stdout).startswith("Usage:")
        assert not result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_args(valid_config, pytestconfig):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            results.pmr,
            args=[
                TestMoveResults.CTRL_SWITCH,
                TestMoveResults.CTRL_TEXT,
                TestMoveResults.USER_SWITCH,
                TestMoveResults.USER_TEXT,
                TestMoveResults.TOKN_SWITCH,
                TestMoveResults.TOKN_TEXT,
                TestMoveResults.PRFX_SWITCH,
                TestMoveResults.PRFX_TEXT,
                TestMoveResults.XZST_SWITCH,
                TestMoveResults.XZST_TEXT,
                TestMoveResults.SWSR_SWITCH,
                TestMoveResults.SWSR_TEXT,
            ],
        )
        assert result.exit_code == 0, f"{result.stderr_bytes}"
        assert result.stderr_bytes

    @staticmethod
    @responses.activate
    def test_move_results(monkeypatch, caplog, pytestconfig):
        monkeypatch.setenv("_pbench_full_hostname", "localhost")
        monkeypatch.setattr(datetime, "datetime", MockDatetime)

        responses.add(
            responses.GET,
            "http://pbench.example.com/api/v1/host_info",
            status=200,
            body="pbench@pbench-server:/srv/pbench/pbench-move-results-receive/fs-version-002",
        )
        responses.add(
            responses.PUT,
            "http://pbench.example.com/api/v1/upload/ctrl/controller",
            status=200,
        )

        ctx = {"args": {"config": os.environ["_PBENCH_AGENT_CONFIG"]}}

        # In order for a pbench tar ball to be moved/copied to a pbench-server
        # the run directory has to have one file in it, a "metadata.log" file.
        # We make a run directory and populate it with our test specific
        # information.
        TMP = pytestconfig.cache.get("TMP", None)
        pbrun = Path(TMP) / "var" / "lib" / "pbench-agent"
        script = "pbench-user-benchmark"
        config = "test-move-results"
        date = "YYYY.MM.DDTHH.MM.SS"
        name = f"{script}_{config}_{date}"
        run_dir = pbrun / name
        run_dir.mkdir(parents=True, exist_ok=True)
        mlog = run_dir / "metadata.log"
        mlog.write_text(mdlog_tmpl.format(**locals()))

        caplog.set_level(logging.DEBUG)

        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            results.pmr,
            args=[
                TestMoveResults.CTRL_SWITCH,
                TestMoveResults.CTRL_TEXT,
                TestMoveResults.USER_SWITCH,
                TestMoveResults.USER_TEXT,
                TestMoveResults.PRFX_SWITCH,
                TestMoveResults.PRFX_TEXT,
            ],
            input=f"{TestMoveResults.TOKN_TEXT}\n",
        )
        assert result.exit_code == 0
        assert result.stdout_bytes
