"""Tests for the Tool Meister "stop" module.
"""
from pbench.agent.tool_meister_stop import RedisServer


class TestRedisServer:
    """Verify the RedisServer class use by Tool Meister "stop"."""

    def test_locally_managed(self, tmp_path):
        # Locally managed means we have a run directory, ...
        rundir = tmp_path / "run-dir"
        rundir.mkdir()
        # ... with a "tm" sub-directory, ...
        tmdir = rundir / "tm"
        tmdir.mkdir()
        # ... containing a "redis.pid" file.
        pidfile = tmdir / "redis.pid"
        pidfile.write_text("12345")

        rs = RedisServer("", rundir, "notme.example.com")
        assert (
            rs.locally_managed()
        ), "Populated run directory did not result in a 'locally managed' RedisServer instance"
        assert (
            rs.host == "localhost"
        ), f"Expected 'RedisServer.host' to be 'localhost', got '{rs.host}'"

    def test_not_locally_managed(self, tmp_path):
        # Empty benchmark run directory indicates not locally managed.
        rundir = tmp_path / "empty-run-dir"
        rundir.mkdir()

        rs_host = "redis.example.com"
        rs = RedisServer(f"{rs_host}:4343", rundir, "notme.example.com")
        assert (
            not rs.locally_managed()
        ), "Empty run directory still resulting in a 'locally managed' RedisServer instance"
        assert (
            rs.host == "redis.example.com"
        ), f"Expected 'RedisServer.host' to be '{rs_host}', got '{rs.host}'"
