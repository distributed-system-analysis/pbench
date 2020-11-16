"""Test PbenchConfig class and objects
"""

import pytest

from pathlib import Path

from pbench import PbenchConfig
from pbench.common.exceptions import BadConfig


_config_path_prefix = Path("lib/pbench/test/common/config")


class TestPbenchConfig:
    def test_empty_config(self):
        config = PbenchConfig(_config_path_prefix / "pbench.cfg")
        assert config.TZ == "UTC", f"Unexpected TZ value, {config.TZ!r}"
        assert (
            config.log_fmt is None
        ), f"Unexpected log format value, {config.log_fmt!r}"
        assert (
            config.default_logging_level == "INFO"
        ), f"Unexpected default logging level, {config.default_logging_level!r}"
        assert (
            config.log_using_caller_directory is False
        ), f"Unexpected 'log using caller directory' boolean, {config.log_using_caller_directory!r}"
        assert config.log_dir is None, f"Unexpected log directory, {config.log_dir!r}"
        assert (
            config.logger_type == "devlog"
        ), f"Unexpected logger type, {config.logger_type!r}"
        with pytest.raises(AttributeError):
            print(f"{config.logger_host!r}")
        with pytest.raises(AttributeError):
            print(f"{config.logger_port!r}")
        assert "42" == config.get(
            "other", "foobar"
        ), "Failed to fetch 'foobar' from 'DEFAULT' section"
        assert "43" == config.get(
            "other", "barfoo"
        ), "Failed to fetch 'barfoo' from 'other' section"
        assert isinstance(
            config.files, list
        ), f"Unexpected object class for 'files', {config.files.__class__!r}"

    def test_log_dir_provided(self):
        config = PbenchConfig(_config_path_prefix / "logdir.cfg")
        assert (
            config.log_dir == "/srv/log/directory"
        ), f"Unexpected log directory, {config.log_dir!r}"

    def test_logger_type_provided(self):
        config = PbenchConfig(_config_path_prefix / "hostport.cfg")
        assert (
            config.logger_type == "hostport"
        ), f"Unexpected logger type, {config.logger_type!r}"
        assert (
            config.logger_host == "logger.example.com"
        ), f"Unexpected logger host value, {config.logger_host!r}"
        assert (
            config.logger_port == "42"
        ), f"Unexpected logger port value, {config.logger_port!r}"

    def test_logger_type_hostport_missing(self):
        with pytest.raises(BadConfig):
            PbenchConfig(_config_path_prefix / "hostport-missing.cfg")
        with pytest.raises(BadConfig):
            PbenchConfig(_config_path_prefix / "hostport-missing-port.cfg")
