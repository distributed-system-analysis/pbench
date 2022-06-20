"""Test PbenchConfig class and objects
"""
import pytest

from configparser import ConfigParser, NoOptionError, NoSectionError
from typing import List, Dict, Any

from pbench import PbenchConfig
from pbench.common import configtools
from pbench.common.exceptions import BadConfig


class MockedConfigParser:
    """Mocked ConfigParser"""

    def __init__(self):
        self._sections = {}

    def get(self, section: str, option: str, fallback=None) -> str:
        """returns value of the given `section` and `option`"""

        if section not in self._sections:
            raise NoSectionError(section)
        if option not in self._sections[section]:
            raise NoOptionError(option, section)
        value = self._sections[section][option]
        if not value:
            if not fallback:
                raise ValueError(option, section)
            else:
                return fallback
        return value


class TestPbenchConfig:
    @staticmethod
    def logger_test_setup(monkeypatch, sections: Dict[str, Any]):
        def mock_ConfigParser_init(self):
            self._sections = sections

        monkeypatch.setattr(configtools, "file_list", TestPbenchConfig.mock_file_list)
        monkeypatch.setattr(ConfigParser, "__init__", mock_ConfigParser_init)
        monkeypatch.setattr(ConfigParser, "get", MockedConfigParser.get)

    def mock_file_list(cfg_name: str) -> List[str]:
        """file_list mock module"""
        return [cfg_name]

    def test_default_logger(self, monkeypatch):
        """Show that PbenchConfig uses default values when NO
        configuration values are provided for `logging`"""

        self.logger_test_setup(monkeypatch, {})
        config = PbenchConfig("pbench.cfg")
        assert config.logger_type == "devlog"
        assert config.log_dir is None
        assert config.log_using_caller_directory is False
        assert config.default_logging_level == "INFO"
        assert config.log_fmt is None
        assert config.TZ == "UTC"

    def test_custom_logger(self, monkeypatch):
        """Show that when configuration values are provided,
        PbenchConfig uses those values instead of default values"""

        logger_type = "file"
        log_dir = "/mock/log_dir"
        logging_level = "Devlog"
        log_format = "1970-01-01T00:00:42.000000 -- 'message'"
        self.logger_test_setup(
            monkeypatch,
            {
                "logging": {
                    "logger_type": logger_type,
                    "log_dir": log_dir,
                    "logging_level": logging_level,
                    "log_format": log_format,
                }
            },
        )
        config = PbenchConfig("pbench.cfg")
        assert config.logger_type == logger_type
        assert config.log_dir == log_dir
        assert config.log_using_caller_directory is False
        assert config.default_logging_level == logging_level
        assert config.log_fmt == log_format
        assert config.TZ == "UTC"

    @pytest.mark.parametrize(
        "config_value, expected_error_msg",
        [
            (
                {"logging": {"logger_type": "hostport"}},
                "No option 'logger_host' in section: 'logging'",
            ),
            (
                {
                    "logging": {
                        "logger_type": "hostport",
                        "logger_host": "logger.example.com",
                    }
                },
                "No option 'logger_port' in section: 'logging'",
            ),
        ],
    )
    def test_logger_hostport_BadConfig(
        self, config_value, expected_error_msg, monkeypatch
    ):
        """Show that PbenchConfig raises 'BadConfig' when the
        configuration does not contain required option."""

        self.logger_test_setup(monkeypatch, config_value)
        with pytest.raises(BadConfig) as exc:
            PbenchConfig("pbench.cfg")
        assert expected_error_msg in str(exc.value)

    @pytest.mark.parametrize(
        "config_value, expected_error_msg",
        [
            (
                {"logging": {"logger_type": "hostport", "logger_host": ""}},
                "ValueError('logger_host', 'logging')",
            ),
            (
                {
                    "logging": {
                        "logger_type": "hostport",
                        "logger_host": "logger.example.com",
                        "logger_port": "",
                    }
                },
                "ValueError('logger_port', 'logging')",
            ),
        ],
    )
    def test_logger_hostport_ValueError(
        self, config_value, expected_error_msg, monkeypatch
    ):
        """Show that PbenchConfig raises 'ValueError' when the
        option contains an empty value."""

        self.logger_test_setup(monkeypatch, config_value)
        with pytest.raises(ValueError) as exc:
            PbenchConfig("pbench.cfg")
        assert expected_error_msg in str(exc)

    def test_logger_hostport(self, monkeypatch):
        """Show that PbenchConfig processes smoothly when the configuration
        contains required values"""

        logger_type = "hostport"
        logger_host = "logger.example.com"
        logger_port = "42"
        self.logger_test_setup(
            monkeypatch,
            {
                "logging": {
                    "logger_type": logger_type,
                    "logger_host": logger_host,
                    "logger_port": logger_port,
                }
            },
        )
        config = PbenchConfig("pbench.cfg")
        assert config.logger_type == logger_type
        assert config.logger_host == logger_host
        assert config.logger_port == logger_port
        assert config.log_dir is None
        assert config.log_using_caller_directory is False
        assert config.default_logging_level == "INFO"
        assert config.log_fmt is None
        assert config.TZ == "UTC"
