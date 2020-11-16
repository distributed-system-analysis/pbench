import datetime
import logging
import os
import responses

from pathlib import Path
from pbench.cli.agent.commands.results import move_results
from pbench.test.agent.task.common import MockDatetime


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
            "http://pbench.example.com/api/v1/upload/ctrl/localhost",
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
        name = "{script}_{config}_{date}"
        run_dir = pbrun / name
        run_dir.mkdir()
        mlog = run_dir / "metadata.log"
        mlog.write_text(mdlog_tmpl.format(**locals()))

        caplog.set_level(logging.DEBUG)

        try:
            runs_copied, failures = move_results(ctx, "pbench", "", True)
        except SystemExit:
            assert False
        assert failures == 0, f"Unexpected failures, {failures}"
        assert runs_copied == 1, f"Unexpected runs_copied, {runs_copied}"
