import pytest
import shutil

from configparser import NoOptionError, NoSectionError
from pathlib import Path

from pbench import PbenchConfig
from pbench.agent import PbenchAgentConfig
from pbench.common.exceptions import BadConfig


class MockedConfigParser:
    """Mocked ConfigParser"""

    def __init__(self):
        self._sections = {
            "pbench-agent": {
                "install-dir": "/mock/install_dir",
                "pbench_run": "/mock/pbench-run",
                "pbench_log": "/mock/pbench.log",
            },
            "results": {
                "scp_opts": "MockStrictHostKeyChecking=no",
                "ssh_opts": "MockStrictHostKeyChecking=no",
            },
        }

    def __getitem__(self, key: str) -> str:
        """check the existence of `key` in config file"""
        if key not in self._sections:
            raise KeyError(key)
        return key

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
        return self._sections[section][option]


class MockPbenchConfig:
    """Mocked PbenchConfig class"""

    def __init__(self, cfg_name: str):
        self.conf = MockedConfigParser()
        self.logger_type = "file"
        self.log_dir = "/mock/log_dir"
        self.files = cfg_name


def mock_is_dir(self) -> bool:
    """Mocked the check if the given path is a directory"""
    return True


def mock_mkdir(self, parents=False, exist_ok=False) -> bool:
    """Mocked the directory creation"""
    if self._accessor and parents == True and exist_ok == True:
        return True
    return False


class TestPbenchAgentConfig:

    config = "/mock/pbench.cfg"

    def test_bad_agent_config(self):
        """test `pbench-agent` section in config file"""
        expected_error_msg = "BadConfig(\"'pbench-agent': []\")"
        with pytest.raises(BadConfig) as e:
            PbenchAgentConfig(self.config)
        assert expected_error_msg in str(e)

    def test_bad_results_config(self, monkeypatch):
        """test `results` section in config file"""

        class Mock_MockedConfigParser:
            def __init__(self):
                self._sections = {
                    "pbench-agent": {},
                }

        expected_error_msg = "BadConfig(\"'results': /mock/pbench.cfg\")"

        monkeypatch.setattr(PbenchConfig, "__init__", MockPbenchConfig.__init__)
        monkeypatch.setattr(
            MockedConfigParser, "__init__", Mock_MockedConfigParser.__init__
        )
        with pytest.raises(BadConfig) as e:
            PbenchAgentConfig(self.config)
        assert expected_error_msg in str(e)

    def test_pbench_run_config(self, monkeypatch):
        """test `pbench_run` option in `pbench-agent` section in config file"""

        class Mock_MockedConfigParser:
            def __init__(self):
                self._sections = {
                    "pbench-agent": {},
                    "results": {},
                }

        expected_error_msg = "BadConfig(\"No option 'pbench_run' in section: 'pbench-agent': /mock/pbench.cfg\")"

        monkeypatch.setattr(PbenchConfig, "__init__", MockPbenchConfig.__init__)
        monkeypatch.setattr(
            MockedConfigParser, "__init__", Mock_MockedConfigParser.__init__
        )
        with pytest.raises(BadConfig) as e:
            PbenchAgentConfig(self.config)
        assert expected_error_msg in str(e)

    def test_pbench_log_config(self, monkeypatch):
        """test `pbench_log` option in `pbench-agent` section in config file"""

        class Mock_MockedConfigParser:
            def __init__(self):
                self._sections = {
                    "pbench-agent": {
                        "pbench_run": "/mock/pbench-run",
                    },
                    "results": {},
                }

        expected_error_msg = "BadConfig(\"No option 'pbench_log' in section: 'pbench-agent': /mock/pbench.cfg\")"

        monkeypatch.setattr(PbenchConfig, "__init__", MockPbenchConfig.__init__)
        monkeypatch.setattr(
            MockedConfigParser, "__init__", Mock_MockedConfigParser.__init__
        )
        with pytest.raises(BadConfig) as e:
            PbenchAgentConfig(self.config)
        assert expected_error_msg in str(e)

    def test_install_dir_config(self, monkeypatch):
        """test `install-dir` option in `pbench-agent` section in config file"""

        class Mock_MockedConfigParser:
            def __init__(self):
                self._sections = {
                    "pbench-agent": {
                        "pbench_run": "/mock/pbench-run",
                        "pbench_log": "/mock/pbench.log",
                    },
                    "results": {},
                }

        expected_error_msg = "BadConfig(\"No option 'install-dir' in section: 'pbench-agent': /mock/pbench.cfg\")"
        monkeypatch.setattr(PbenchConfig, "__init__", MockPbenchConfig.__init__)
        monkeypatch.setattr(
            MockedConfigParser, "__init__", Mock_MockedConfigParser.__init__
        )
        with pytest.raises(BadConfig) as e:
            PbenchAgentConfig(self.config)
        assert expected_error_msg in str(e)

    def test_install_dir_exist(self, monkeypatch):
        """Verify Installation Directory"""

        class Mock_MockedConfigParser:
            def __init__(self):
                self._sections = {
                    "pbench-agent": {
                        "install-dir": "/mock/install_dir",
                        "pbench_run": "/mock/pbench-run",
                        "pbench_log": "/mock/pbench.log",
                    },
                    "results": {},
                }

        expected_error_msg = "BadConfig(\"pbench installation directory, '/mock/install_dir', does not exist\")"

        monkeypatch.setattr(PbenchConfig, "__init__", MockPbenchConfig.__init__)
        monkeypatch.setattr(
            MockedConfigParser, "__init__", Mock_MockedConfigParser.__init__
        )
        with pytest.raises(BadConfig) as e:
            PbenchAgentConfig(self.config)
        assert expected_error_msg in str(e)

    def test_install_dir_directory_creation(self, monkeypatch):
        """Verify creating Installation Directory"""

        class Mock_MockedConfigParser:
            def __init__(self):
                self._sections = {
                    "pbench-agent": {
                        "install-dir": "/mock/install_dir",
                        "pbench_run": "/mock/pbench-run",
                        "pbench_log": "/mock/pbench.log",
                    },
                    "results": {},
                }

        expected_error_msg = (
            "BadConfig(\"[Errno 2] No such file or directory: '/mock/pbench-run'\")"
        )

        monkeypatch.setattr(PbenchConfig, "__init__", MockPbenchConfig.__init__)
        monkeypatch.setattr(
            MockedConfigParser, "__init__", Mock_MockedConfigParser.__init__
        )
        monkeypatch.setattr(Path, "is_dir", mock_is_dir)
        with pytest.raises(BadConfig) as e:
            PbenchAgentConfig(self.config)
        assert expected_error_msg in str(e)

    def test_valid_PbenchAgentConfig(self, monkeypatch):
        """Verify Valid Config file"""
        config = "/mock/pbench.cfg"
        monkeypatch.setattr(PbenchConfig, "__init__", MockPbenchConfig.__init__)
        monkeypatch.setattr(Path, "is_dir", mock_is_dir)
        monkeypatch.setattr(Path, "mkdir", mock_mkdir)
        PbenchAgentConfig(config)


def test_invalid_config(setup):
    """Verify Invalid Config File"""
    shutil.copyfile(
        "./lib/pbench/test/unit/agent/config/pbench-agent.invalid.cfg",
        str(setup["cfg_dir"] / "pbench-agent.invalid.cfg"),
    )
    with pytest.raises(BadConfig):
        PbenchAgentConfig(setup["cfg_dir"] / "pbench-agent.invalid.cfg")
