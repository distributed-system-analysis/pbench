import datetime
import responses

from pbench.agent.config import AgentConfig
from pbench.agent.task.move_results import move_results
from pbench.test.agent.task.common import MockDatetime, mock_agent_config


class TestMoveResults:
    @staticmethod
    @responses.activate
    def test_move_results(monkeypatch):
        monkeypatch.setenv("pbench_tmp", "/tmp")
        monkeypatch.setenv("full_hostname", "localhost")
        monkeypatch.setattr(datetime, "datetime", MockDatetime)
        monkeypatch.setattr(AgentConfig, "get_agent", mock_agent_config)

        responses.add(
            responses.GET,
            "http://pbench.example.com/api/v1/host_info",
            status=200,
            body="pbench@pbench-server:/srv/pbench/pbench-move-results-receive/fs-version-002",
        )
        responses.add(
            responses.POST, "http://pbench.example.com/api/v1/upload", status=200
        )

        try:
            move_results("pbench", "", True)
        except SystemExit:
            assert False
        assert True
