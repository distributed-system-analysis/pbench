"""Test the Gunicorn driver module, `shell`, to ensure it is usable."""
from configparser import NoOptionError, NoSectionError
import logging
import os
from pathlib import Path
import subprocess
from typing import Callable, Optional, Union

from flask import Flask
import pytest

import pbench.cli.server.shell as shell
from pbench.common.exceptions import BadConfig, ConfigFileNotSpecified
from pbench.server import PbenchServerConfig
from pbench.server.auth import OpenIDClient


@pytest.fixture
def mock_get_server_config(monkeypatch, server_config):
    def get_server_config() -> PbenchServerConfig:
        return server_config

    monkeypatch.setattr(shell, "get_server_config", get_server_config)


def exists_false(theself: Path) -> bool:
    """Mock Path.exists() returning False."""
    return False


def exists_true(theself: Path) -> bool:
    """Mock Path.exists() returning False."""
    return True


class FakeIndexer:

    status = 0
    called = []

    def __init__(self, bin_dir: Path, cwd: Path, logger: logging.Logger):
        self.bin_dir = bin_dir
        self.cwd = cwd
        self.logger = logger

    def start(self):
        """Start an indexer subprocess.

        The indexer will run in the background, periodically checking for datasets
        with the INDEX operation enabled. It will loop until it finds no more, and
        then sleep for a while before trying again.

        Args:
            bin_dir: Where to find the pbench-index command
            cwd: Where to set the working directory
            logger: A Python logger

        Returns:
            The Popen of the created process so it can be tracked and stopped.
        """
        self.called.append("start")

    def shutdown(self):
        """Stop the indexer

        TODO: We're stopping with SIGTERM, which will interrupt any indexing
        in progress in favor of a quicker shutdown. We could instead send a
        """

        self.called.append("shutdown")
        return self.status

    @classmethod
    def reset(cls):
        cls.called.clear()
        cls.status = 0


@pytest.fixture
def mock_indexer(monkeypatch, server_config):
    FakeIndexer.reset()
    monkeypatch.setattr("pbench.cli.server.shell.PbenchIndexer", FakeIndexer)


class FakePopen:

    processes = []
    pid = 0

    def __init__(self, args: list[Union[str, Path]], cwd: Path):
        self.processes.append((" ".join(str(a) for a in args), cwd))
        self.running = True
        self.waited = False
        self.pid = self.pid
        __class__.pid += 1

    def terminate(self):
        self.running = False

    def wait(self, timeout: float = 0.0):
        self.waited = True


class FakeThread:

    threads = []

    def __init__(self, target: Callable, daemon: bool):
        self.threads.append((target, daemon))
        self.target = target
        self.daemon = daemon
        self.started = False
        self.joined = False

    def start(self):
        self.started = True

    def join(self, timeout: float = 0.0):
        self.joined = True


class TestShell:
    @staticmethod
    def test_app_normal(monkeypatch, mock_get_server_config):
        """Test site.app() success case"""

        def mocked_create_app(config: PbenchServerConfig):
            return Flask("fake")

        monkeypatch.setattr(shell, "create_app", mocked_create_app)

        app = shell.app()

        assert app.name == "fake"

    @staticmethod
    def test_find_the_unicorn(monkeypatch, make_logger):
        """Test site.find_the_unicorn success and failure cases"""
        # Only need to set this once since the second test will change it.
        monkeypatch.setenv("PATH", "ONE:TWO")

        # Cause the `.exists()` check for gunicorn to fail resulting in no
        # change to the `PATH` environment variable.
        monkeypatch.setattr(Path, "exists", exists_false)
        shell.find_the_unicorn(make_logger)
        assert (
            os.environ["PATH"] == "ONE:TWO"
        ), f"Expected PATH == 'ONE:TWO', found PATH == '{os.environ['PATH']}'"

        # Cause the `.exists()` check for gunicorn to succeed, resulting in an
        # added `PATH` element.
        monkeypatch.setattr(Path, "exists", exists_true)
        shell.find_the_unicorn(make_logger)
        assert os.environ["PATH"].endswith(
            "/bin:ONE:TWO"
        ), f"Expected PATH to end with '/bin:ONE:TWO', found PATH == '{os.environ['PATH']}'"

    @staticmethod
    def test_indexers(monkeypatch, make_logger):
        """Test startup and shutdown of the indexers"""
        monkeypatch.setattr("pbench.cli.server.shell.subprocess.Popen", FakePopen)
        monkeypatch.setattr("pbench.cli.server.shell.Thread", FakeThread)

        indexer = shell.PbenchIndexer(
            bin_dir=Path("/bin"), cwd=Path("/cwd"), logger=make_logger
        )
        assert indexer.indexer is None
        assert indexer.reindexer is None

        indexer.start()
        assert FakePopen.processes == [
            ("python3 /bin/pbench-index", Path("/cwd")),
            ("python3 /bin/pbench-index --re-index", Path("/cwd")),
        ]
        assert indexer.indexer.running
        assert not indexer.indexer.waited
        assert indexer.reindexer.running
        assert not indexer.reindexer.waited
        assert indexer.reaper.daemon
        assert indexer.reaper.started
        assert not indexer.reaper.joined

        indexer.shutdown()
        assert not indexer.indexer.running
        assert indexer.indexer.waited
        assert not indexer.reindexer.running
        assert indexer.reindexer.waited
        assert indexer.reaper.started
        assert indexer.reaper.joined

    @staticmethod
    @pytest.mark.parametrize("user_site", [False, True])
    @pytest.mark.parametrize("oidc_conf", [False, True])
    def test_main(
        monkeypatch,
        make_logger,
        mock_get_server_config,
        mock_indexer,
        user_site,
        oidc_conf,
    ):
        called = []

        def find_the_unicorn(logger: logging.Logger):
            called.append("find_the_unicorn")

        def wait_for_uri(*args, **kwargs):
            called.append(f"wait_for_uri({args[0]},{args[1]})")

        def init_indexing(*args, **kwargs):
            called.append("init_indexing")

        def wait_for_oidc_server(
            server_config: PbenchServerConfig, logger: logging.Logger
        ) -> str:
            if oidc_conf:
                return "https://oidc.example.com"
            else:
                raise OpenIDClient.NotConfigured()

        commands = []

        def run(args, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
            commands.append(args)
            ret_val = 42 if args[0] == "gunicorn" else 0
            return subprocess.CompletedProcess(args, ret_val)

        monkeypatch.setattr(shell.site, "ENABLE_USER_SITE", user_site)
        monkeypatch.setattr(shell, "find_the_unicorn", find_the_unicorn)
        monkeypatch.setattr(shell, "wait_for_uri", wait_for_uri)
        monkeypatch.setattr(shell, "init_indexing", init_indexing)
        monkeypatch.setattr(
            shell.OpenIDClient, "wait_for_oidc_server", wait_for_oidc_server
        )
        monkeypatch.setattr(subprocess, "run", run)

        ret_val = shell.main()

        assert ret_val == 42
        expected_called = ["find_the_unicorn"] if user_site else []
        expected_called += [
            "wait_for_uri(sqlite:///:memory:,120)",
            "wait_for_uri(http://elasticsearch.example.com:7080,120)",
            "init_indexing",
        ]
        assert called == expected_called
        assert FakeIndexer.called == ["start", "shutdown"]
        assert len(commands) == 1, f"{commands!r}"
        gunicorn_command = commands[0]
        assert gunicorn_command[-1] == "pbench.cli.server.shell:app()", f"{commands!r}"
        gunicorn_command = gunicorn_command[:-1]
        if user_site:
            assert (
                gunicorn_command[-2:][0] == "--pythonpath"
            ), f"commands[2] = {commands[2]!r}"
            gunicorn_command = gunicorn_command[:-2]
        expected_command = [
            "gunicorn",
            "--workers",
            "3",
            "--timeout",
            "9000",
            "--pid",
            "/run/pbench-server/gunicorn.pid",
            "--bind",
            "0.0.0.0:8001",
            "--log-syslog",
            "--log-syslog-prefix",
            "pbench-server",
        ]
        assert (
            gunicorn_command == expected_command
        ), f"expected_command = {expected_command!r}, commands[2] = {commands[2]!r}"

    @staticmethod
    @pytest.mark.parametrize(
        "init_indexing_exc",
        [NoSectionError("missingsection"), NoOptionError("section", "missingoption")],
    )
    def test_main_init_indexing_failed(
        monkeypatch,
        make_logger,
        mock_get_server_config,
        init_indexing_exc,
        mock_indexer,
    ):
        def immediate_success(*args, **kwargs):
            pass

        called = [False]

        def init_indexing(*args, **kwargs) -> int:
            called[0] = True
            raise init_indexing_exc

        monkeypatch.setattr(shell.site, "ENABLE_USER_SITE", False)
        monkeypatch.setattr(shell, "wait_for_uri", immediate_success)
        monkeypatch.setattr(shell, "init_indexing", init_indexing)

        ret_val = shell.main()

        assert called[0]
        assert ret_val == 1

    @staticmethod
    @pytest.mark.parametrize(
        "init_db_exc",
        [NoSectionError("missingsection"), NoOptionError("section", "missingoption")],
    )
    def test_main_initdb_failed(
        monkeypatch, make_logger, mock_get_server_config, init_db_exc
    ):
        def immediate_success(*args, **kwargs):
            pass

        called = [False]

        def init_db(*args, **kwargs) -> int:
            called[0] = True
            raise init_db_exc

        monkeypatch.setattr(shell.site, "ENABLE_USER_SITE", False)
        monkeypatch.setattr(shell, "wait_for_uri", immediate_success)
        monkeypatch.setattr(shell, "init_db", init_db)

        ret_val = shell.main()

        assert called[0]
        assert ret_val == 1

    @staticmethod
    def test_main_wait_for_oidc_server_exc(
        monkeypatch, make_logger, mock_get_server_config
    ):
        def immediate_success(*args, **kwargs):
            pass

        called = [False]

        def wait_for_oidc_server(
            server_config: PbenchServerConfig, logger: logging.Logger
        ) -> str:
            called[0] = True
            raise Exception("oidc exception")

        monkeypatch.setattr(shell.site, "ENABLE_USER_SITE", False)
        monkeypatch.setattr(shell, "wait_for_uri", immediate_success)
        monkeypatch.setattr(
            shell.OpenIDClient, "wait_for_oidc_server", wait_for_oidc_server
        )

        ret_val = shell.main()

        assert called[0]
        assert ret_val == 1

    @staticmethod
    @pytest.mark.parametrize(
        "wait_for_uri_exc",
        [
            ConnectionRefusedError("elasticsearch exception"),
            BadConfig("elasticsearch config"),
        ],
    )
    def test_main_wait_for_elasticsearch_exc(
        monkeypatch, make_logger, mock_get_server_config, wait_for_uri_exc
    ):
        called = [0]
        raised = [False]

        def wait_for_uri(
            server_config: PbenchServerConfig, logger: logging.Logger
        ) -> str:
            called[0] += 1
            if called[0] > 1:
                raised[0] = True
                raise wait_for_uri_exc

        monkeypatch.setattr(shell.site, "ENABLE_USER_SITE", False)
        monkeypatch.setattr(shell, "wait_for_uri", wait_for_uri)

        ret_val = shell.main()

        assert called[0] == 2 and raised[0]
        assert ret_val == 1

    @staticmethod
    @pytest.mark.parametrize(
        "wait_for_uri_exc",
        [ConnectionRefusedError("database exception"), BadConfig("database config")],
    )
    def test_main_wait_for_database_exc(
        monkeypatch, make_logger, mock_get_server_config, wait_for_uri_exc
    ):
        called = [False]

        def wait_for_uri(
            server_config: PbenchServerConfig, logger: logging.Logger
        ) -> str:
            called[0] = True
            raise wait_for_uri_exc

        monkeypatch.setattr(shell.site, "ENABLE_USER_SITE", False)
        monkeypatch.setattr(shell, "wait_for_uri", wait_for_uri)

        ret_val = shell.main()

        assert called[0]
        assert ret_val == 1

    @staticmethod
    @pytest.mark.parametrize("section", ["database", "pbench-server"])
    def test_main_server_config_no_section(
        monkeypatch, on_disk_server_config, make_logger, section
    ):
        def get_server_config() -> PbenchServerConfig:
            cfg_file = on_disk_server_config["cfg_dir"] / "pbench-server.cfg"
            config = PbenchServerConfig(str(cfg_file))
            del config._conf[section]
            return config

        monkeypatch.setattr(shell, "get_server_config", get_server_config)

        ret_val = shell.main()

        assert ret_val == 1

    @staticmethod
    @pytest.mark.parametrize(
        "option",
        [
            "bind_host",
            "bind_port",
            "uri",
            "wait_timeout",
            "workers",
            "worker_timeout",
            "crontab-dir",
        ],
    )
    def test_main_server_config_no_option(
        monkeypatch, on_disk_server_config, make_logger, option
    ):
        def get_server_config() -> PbenchServerConfig:
            cfg_file = on_disk_server_config["cfg_dir"] / "pbench-server.cfg"
            config = PbenchServerConfig(str(cfg_file))
            section = (
                "database"
                if option in frozenset(("uri", "wait_timeout"))
                else "DEFAULT"
                if option == "crontab-dir"
                else "pbench-server"
            )
            make_logger.error(config._conf[section][option])
            del config._conf[section][option]
            return config

        monkeypatch.setattr(shell, "get_server_config", get_server_config)

        ret_val = shell.main()

        assert ret_val == 1

    @staticmethod
    @pytest.mark.parametrize(
        "gsc_exc",
        [ConfigFileNotSpecified("nofile found"), BadConfig("bad to the bone")],
    )
    def test_main_get_server_config_exc(capsys, monkeypatch, make_logger, gsc_exc):
        called = [False]

        def get_server_config() -> PbenchServerConfig:
            called[0] = True
            raise gsc_exc

        monkeypatch.setattr(shell, "get_server_config", get_server_config)

        ret_val = shell.main()

        assert called[0]
        assert ret_val == 1
        out, err = capsys.readouterr()
        assert err.startswith(str(gsc_exc)), f"out={out!r}, err={err!r}"
