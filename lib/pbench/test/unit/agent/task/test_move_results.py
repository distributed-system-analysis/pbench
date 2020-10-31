import os
import datetime
import responses

from pbench.cli.agent.commands.results import move_results
from pbench.test.unit.agent.task.common import MockDatetime


class TestMoveResults:
    @staticmethod
    @responses.activate
    def test_move_results(monkeypatch):
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

        try:
            move_results(ctx, "pbench", "", True)
        except SystemExit:
            assert False
        assert True
