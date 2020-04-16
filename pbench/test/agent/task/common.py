import datetime
import tempfile

FAKE_TIME = datetime.datetime(2020, 2, 2, 22, 0, 0)
target_dir = tempfile.mkdtemp()
tarball = "pbench/test/agent/fixtures/copy_result_tb/log.tar.xz"
bad_tarball = "nothing.tar.xz"

MRT_DIR = "pbench/test/agent/fixtures/make_result_tb"


class MockDatetime(datetime.datetime):
    @classmethod
    def now(cls, **kwargs):
        return FAKE_TIME


def mock_agent_config(*args, **kwargs):
    return {"pbench_run": "pbench/test/agent/fixtures/move_results"}
