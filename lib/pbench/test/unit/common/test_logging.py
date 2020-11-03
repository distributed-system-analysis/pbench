"""Test Pbench Logging Infrastructure
"""

import logging
import pytest
import tempfile

from pathlib import Path

from pbench import PbenchConfig
from pbench.common.exceptions import BadConfig
from pbench.common.logger import get_pbench_logger, _handlers


class TestLoggingSetup:
    @pytest.fixture(autouse=True)
    def config(self):
        # Setup the configuration
        config_prefix_path = Path("lib/pbench/test/unit/common/config/")
        self.config = PbenchConfig(config_prefix_path / "pbench.cfg")
        self.logger = None
        yield
        # Teardown the setup
        self.config = None
        self.logger = None

    def test_log_messages_bad_logger_type(self):
        """Test unsupported logger type."""
        self.config.logger_type = "badtype"
        with pytest.raises(BadConfig):
            self.logger = get_pbench_logger("bad_logger", self.config)

    def test_log_messages_to_file(self):
        """Test to log messages to a file."""
        # Was test-26.1, via test_logger_type.py
        fname = "test_log_messages_to_file"
        assert (
            self.config.logger_type == "devlog"
        ), f"Unexpected logger type encountered, '{self.config.logger_type}', expected 'file'"
        self.config.logger_type = "file"
        with tempfile.TemporaryDirectory(
            suffix=".d", prefix="pbench-common-unit-tests."
        ) as TMP:
            self.config.log_dir = str(Path(TMP) / "log-dir")
            assert not Path(self.config.log_dir).exists()
            self.logger = get_pbench_logger(fname, self.config)
            assert Path(
                self.config.log_dir
            ).is_dir(), f"Missing logging directory, {self.config.log_dir}"
            assert _handlers[fname] == self.logger.logger.handlers[0]
            assert (
                _handlers[fname].__class__.__name__ == "FileHandler"
            ), f"Unexpected handler set, {_handlers[fname].__class__.__name__!r}"

    def test_log_messages_to_file_pre_exist_dir(self):
        """Test to log messages to a file."""
        # Was test-26.1, via test_logger_type.py
        fname = "test_log_messages_to_file_pre_exist_dir"
        assert (
            self.config.logger_type == "devlog"
        ), f"Unexpected logger type encountered, '{self.config.logger_type}', expected 'file'"
        self.config.logger_type = "file"
        with tempfile.TemporaryDirectory(
            suffix=".d", prefix="pbench-common-unit-tests."
        ) as TMP:
            assert Path(TMP).exists()
            self.config.log_dir = str(Path(TMP) / "log-dir")
            assert not Path(
                self.config.log_dir
            ).exists(), (
                f"Test logging directory unexpectedly exists, {self.config.log_dir}"
            )
            Path(self.config.log_dir).mkdir()
            self.logger = get_pbench_logger(fname, self.config)
            assert Path(
                self.config.log_dir
            ).is_dir(), f"Missing logging directory, {self.config.log_dir}"
            assert _handlers[fname] == self.logger.logger.handlers[0]
            assert (
                _handlers[fname].__class__.__name__ == "FileHandler"
            ), f"Unexpected handler set, {_handlers[fname].__class__.__name__!r}"

    def test_log_messages_to_devlog(self):
        """Test to log messages via /dev/log"""
        # Was test-26.2, via test_logger_type.py
        fname = "test_log_messages_to_devlog"
        self.logger = get_pbench_logger(fname, self.config)
        assert (
            self.config.logger_type == "devlog"
        ), f"Unexpected logger type encountered, '{self.config.logger_type}', expected 'devlog'"
        assert (
            self.config.log_dir is None
        ), f"Unexpected log directory configuration found, {self.config_log_dir}"
        assert _handlers[fname] == self.logger.logger.handlers[0]
        assert (
            _handlers[fname].__class__.__name__ == "SysLogHandler"
        ), f"Unexpected handler set for {fname}, {_handlers[fname].__class__.__name__!r}"
        assert (
            _handlers[fname].address == "/dev/log"
        ), f"Unexpected handler address set, {_handlers[fname].address!r}"

    def test_log_messages_to_hostport(self):
        """Test to check error when logger_port and logger_host are not provided with "hostport"."""
        # Was test-26.3, via test_logger_type.py
        fname = "test_log_messages_to_hostport"
        self.config.logger_type = "hostport"
        self.config.logger_host = "localhost"
        self.config.logger_port = "42"
        self.logger = get_pbench_logger(fname, self.config)
        assert (
            self.config.logger_type == "hostport"
        ), f"Unexpected logger type encountered, '{self.config.logger_type}', expected 'hostport'"
        assert (
            self.config.log_dir is None
        ), f"Unexpected log directory configuration found, {self.config_log_dir}"
        assert _handlers[fname] == self.logger.logger.handlers[0]
        assert (
            _handlers[fname].__class__.__name__ == "SysLogHandler"
        ), f"Unexpected handler set, {_handlers[fname].__class__.__name__!r}"
        assert (
            _handlers[fname].address[0] == "localhost"
            and _handlers[fname].address[1] == 42
        ), f"Unexpected handler address set, {_handlers[fname].address!r}"

    def test_log_level(self):
        """Test to verify log level setting."""
        # Was test-26.5, test_logger_level.py
        config_prefix_path = Path("lib/pbench/test/unit/common/config/")
        config = PbenchConfig(config_prefix_path / "log-level.cfg")
        logger = get_pbench_logger("test_log_level", config)
        assert (
            config.logger_type == "devlog"
        ), f"Unexpected logger type encountered, '{config.logger_type}', expected 'devlog'"
        assert (
            logger.logger.getEffectiveLevel() == logging.INFO
        ), f"Unexpected default logging level, {logger.logger.getEffectiveLevel()}"
        logger = get_pbench_logger("other", config)
        assert (
            logger.logger.getEffectiveLevel() == logging.CRITICAL
        ), f"Unexpected logging level, {logger.logger.getEffectiveLevel()}"
