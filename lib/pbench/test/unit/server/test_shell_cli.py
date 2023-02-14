"""Test the Gunicorn driver module, `shell`, to ensure it is usable."""
from configparser import NoOptionError, NoSectionError
import logging
import os
from pathlib import Path
import subprocess
from typing import Optional

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
    def test_generate_crontab_if_necessary_no_action(monkeypatch, make_logger):
        """Test site.generate_crontab_if_necessary with no action taken"""

        called = {"run": False}

        def run(args, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
            called["run"] = True

        monkeypatch.setenv("PATH", "one:two")
        # An existing crontab does nothing.
        monkeypatch.setattr(Path, "exists", exists_true)
        monkeypatch.setattr(subprocess, "run", run)

        ret_val = shell.generate_crontab_if_necessary(
            "/tmp", Path("bindir"), "cwd", make_logger
        )

        assert ret_val == 0
        assert os.environ["PATH"] == "one:two", f"PATH='{os.environ['PATH']}'"
        assert not called[
            "run"
        ], "generate_crontab_if_necessary() took action unexpectedly"

    @staticmethod
    def test_generate_crontab_if_necessary_created(monkeypatch, make_logger):
        """Test site.generate_crontab_if_necessary creating the crontab"""

        commands = []

        def run_success(args, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
            commands.append(args)
            return subprocess.CompletedProcess(args, 0)

        monkeypatch.setenv("PATH", "a:b")
        # We don't have an existing crontab
        monkeypatch.setattr(Path, "exists", exists_false)
        monkeypatch.setattr(subprocess, "run", run_success)

        ret_val = shell.generate_crontab_if_necessary(
            "/tmp", Path("bindir"), "cwd", make_logger
        )

        assert ret_val == 0
        assert os.environ["PATH"] == "bindir:a:b", f"PATH='{os.environ['PATH']}'"
        assert commands == [
            ["pbench-create-crontab", "/tmp"],
            ["crontab", "/tmp/crontab"],
        ]

    @staticmethod
    def test_generate_crontab_if_necessary_create_failed(monkeypatch, make_logger):
        monkeypatch.setenv("PATH", "a:b")

        unlink_record = []

        def unlink(*args, **kwargs):
            unlink_record.append("unlink")

        monkeypatch.setattr(Path, "unlink", unlink)

        commands = []

        def run(args, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
            commands.append(args)
            return subprocess.CompletedProcess(args, 1)

        # We don't have an existing crontab
        monkeypatch.setattr(Path, "exists", exists_false)
        monkeypatch.setattr(subprocess, "run", run)

        ret_val = shell.generate_crontab_if_necessary(
            "/tmp", Path("bindir"), "cwd", make_logger
        )

        assert ret_val == 1
        assert os.environ["PATH"] == "bindir:a:b", f"PATH='{os.environ['PATH']}'"
        assert commands == [["pbench-create-crontab", "/tmp"]]
        assert unlink_record == ["unlink"]

    @staticmethod
    def test_generate_crontab_if_necessary_crontab_failed(monkeypatch, make_logger):
        monkeypatch.setenv("PATH", "a:b")

        unlink_record = []

        def unlink(*args, **kwargs):
            unlink_record.append("unlink")

        monkeypatch.setattr(Path, "unlink", unlink)

        commands = []

        def run(args, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
            commands.append(args)
            ret_val = 1 if args[0] == "crontab" else 0
            return subprocess.CompletedProcess(args, ret_val)

        # We don't have an existing crontab
        monkeypatch.setattr(Path, "exists", exists_false)
        monkeypatch.setattr(subprocess, "run", run)

        ret_val = shell.generate_crontab_if_necessary(
            "/tmp", Path("bindir"), "cwd", make_logger
        )

        assert ret_val == 1
        assert os.environ["PATH"] == "bindir:a:b", f"PATH='{os.environ['PATH']}'"
        assert commands == [
            ["pbench-create-crontab", "/tmp"],
            ["crontab", "/tmp/crontab"],
        ]
        assert unlink_record == ["unlink"]

    @staticmethod
    @pytest.mark.parametrize("user_site", [False, True])
    @pytest.mark.parametrize("oidc_conf", [False, True])
    def test_main(
        monkeypatch, make_logger, mock_get_server_config, user_site, oidc_conf
    ):
        called = []

        def find_the_unicorn(logger: logging.Logger):
            called.append("find_the_unicorn")

        def wait_for_uri(*args, **kwargs):
            called.append("wait_for_uri")

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
        monkeypatch.setattr(
            shell.OpenIDClient, "wait_for_oidc_server", wait_for_oidc_server
        )
        monkeypatch.setattr(subprocess, "run", run)

        ret_val = shell.main()

        assert ret_val == 42
        assert not user_site or called[0] == "find_the_unicorn"
        assert called[-2] == "wait_for_uri"
        assert called[-2] == called[-1]
        assert len(commands) == 3, f"{commands!r}"
        assert commands[0][0] == "pbench-create-crontab"
        assert commands[1][0] == "crontab"
        gunicorn_command = commands[2]
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
    def test_main_crontab_failed(monkeypatch, make_logger, mock_get_server_config):
        def noop(*args, **kwargs):
            pass

        def generate_crontab_if_necessary(*args, **kwargs) -> int:
            return 43

        monkeypatch.setattr(shell.site, "ENABLE_USER_SITE", False)
        monkeypatch.setattr(shell, "wait_for_uri", noop)
        monkeypatch.setattr(
            shell, "generate_crontab_if_necessary", generate_crontab_if_necessary
        )

        ret_val = shell.main()

        assert ret_val == 43

    @staticmethod
    @pytest.mark.parametrize("init_db_exc", ["section", "option"])
    def test_main_initdb_failed(
        monkeypatch, make_logger, mock_get_server_config, init_db_exc
    ):
        def init_db(*args, **kwargs) -> int:
            if init_db_exc == "section":
                exc = NoSectionError("missingsection")
            elif init_db_exc == "option":
                exc = NoOptionError("section", "missingoption")
            else:
                exc = Exception(f"Bad test parameter, {init_db_exc}")
            raise exc

        monkeypatch.setattr(shell.site, "ENABLE_USER_SITE", False)
        monkeypatch.setattr(shell, "init_db", init_db)

        ret_val = shell.main()

        assert ret_val == 1

    @staticmethod
    def test_main_wait_for_oidc_server_exc(
        monkeypatch, make_logger, mock_get_server_config
    ):
        def wait_for_oidc_server(
            server_config: PbenchServerConfig, logger: logging.Logger
        ) -> str:
            raise Exception("oidc exception")

        monkeypatch.setattr(shell.site, "ENABLE_USER_SITE", False)
        monkeypatch.setattr(
            shell.OpenIDClient, "wait_for_oidc_server", wait_for_oidc_server
        )

        ret_val = shell.main()

        assert ret_val == 1

    @staticmethod
    def test_main_wait_for_database_exc(
        monkeypatch, make_logger, mock_get_server_config
    ):
        def wait_for_uri(
            server_config: PbenchServerConfig, logger: logging.Logger
        ) -> str:
            raise ConnectionRefusedError("database exception")

        monkeypatch.setattr(shell.site, "ENABLE_USER_SITE", False)
        monkeypatch.setattr(shell, "wait_for_uri", wait_for_uri)

        ret_val = shell.main()

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
    @pytest.mark.parametrize("gsc_exc", ["nofile", "bad"])
    def test_main_get_server_config_exc(capsys, monkeypatch, make_logger, gsc_exc):
        def get_server_config() -> PbenchServerConfig:
            if gsc_exc == "nofile":
                exc = ConfigFileNotSpecified("nofile found")
            elif gsc_exc == "bad":
                exc = BadConfig("bad to the bone")
            else:
                exc = Exception(f"Bad test parameter, {gsc_exc}")
            raise exc

        monkeypatch.setattr(shell, "get_server_config", get_server_config)

        ret_val = shell.main()

        assert ret_val == 1
        out, err = capsys.readouterr()
        assert err.startswith(gsc_exc), f"out={out!r}, err={err!r}"
