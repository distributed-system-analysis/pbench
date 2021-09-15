import os
import logging
import pytest

from pathlib import Path
from typing import List

from pbench.process_tb import ProcessTb, Results


class MockConfig:
    TS = "run-1970-01-02T00:00:00.000000"

    def __init__(self, mappings: dict):
        self.mappings = mappings

    def get(self, section: str, option: str) -> str:
        assert (
            section in self.mappings and option in self.mappings[section]
        ), f"Unexpected configuration option, {section!r}/{option!r}, in MockConfig.get()"
        return self.mappings[section][option]


class TestProcessTb:

    receive_dir = "/srv/pbench/pbench-results-receive-dir"

    def test_token(self, logger):
        expected_error_msg = (
            "No value for config option put-token in section pbench-server"
        )
        mappings = {"pbench-server": {"put-token": ""}}
        with pytest.raises(ValueError) as e:
            ProcessTb(MockConfig(mappings), logger)

        assert expected_error_msg in str(e)

    def test_get_receive_dir_failed(self, monkeypatch, logger):
        def mock_is_dir(self) -> bool:
            assert False, f"Unexpected call to mocked Path.is_dir()"

        expected_error_msg = "Failed: No value for config option pbench-receive-dir-prefix in section pbench-server"
        mappings = {
            "pbench-server": {
                "pbench-receive-dir-prefix": "",
                "put-token": "Authorization-token",
            }
        }
        monkeypatch.setattr(Path, "is_dir", mock_is_dir)
        with pytest.raises(ValueError) as e:
            ProcessTb(MockConfig(mappings), logger)

        assert expected_error_msg in str(e)

    def test_get_receive_dir_value_failed(self, logger):
        wrong_dir = "/srv/wrong-directory"
        expected_error_msg = (
            f"Failed: '{wrong_dir}-002' does not exist, or is not a directory"
        )
        mappings = {
            "pbench-server": {
                "pbench-receive-dir-prefix": wrong_dir,
                "put-token": "Authorization-token",
            }
        }
        with pytest.raises(NotADirectoryError) as e:
            ProcessTb(MockConfig(mappings), logger)

        assert expected_error_msg in str(e)

    def test_process_tb_file_not_found_error(self, monkeypatch, caplog, logger):
        """checks normal processing when tar ball is not present"""
        receive_path = Path(TestProcessTb.receive_dir + "-002")
        bad_tarball = "bad_log.tar.xz"
        bad_tb = receive_path / bad_tarball

        def mock_is_dir(self) -> bool:
            assert self == receive_path, f"Unexpected Results directory: {str(self)!r}"
            return True

        def mock_glob(self: Path, pattern: str) -> List[Path]:
            assert self == receive_path and pattern == "**/*.tar.xz.md5"
            return [receive_path / (bad_tarball + ".md5")]

        def mock_results_push(ctrl: str, tb: Path, token: str) -> None:
            assert (
                tb == bad_tb
            ), f"Unexpected tar ball, {tb!r} in mocked results_push function"
            raise FileNotFoundError(f"No such file or directory: '{tb.name}'")

        expected_result = Results(nstatus="", ntotal=1, ntbs=0, nerr=1)
        mappings = {
            "pbench-server": {
                "pbench-receive-dir-prefix": TestProcessTb.receive_dir,
                "put-token": "Authorization-token",
            }
        }
        expected_error_msg = f"No such file or directory: '{bad_tarball}'"
        monkeypatch.setattr(Path, "is_dir", mock_is_dir)
        monkeypatch.setattr(Path, "glob", mock_glob)
        monkeypatch.setattr(ProcessTb, "_results_push", mock_results_push)
        ptb = ProcessTb(MockConfig(mappings), logger)
        res = ptb.process_tb()

        assert res == expected_result
        assert expected_error_msg in caplog.text

    def test_process_tb_connection_error(self, monkeypatch, caplog, logger):
        """checks normal processing when Connection Error is faced"""
        receive_path = Path(TestProcessTb.receive_dir + "-002")
        tarball = "log.tar.xz"
        good_tb = receive_path / tarball

        def mock_is_dir(self) -> bool:
            assert self == receive_path, f"Unexpected Results directory: {str(self)!r}"
            return True

        def mock_glob(self: Path, pattern: str) -> List[Path]:
            assert self == receive_path and pattern == "**/*.tar.xz.md5"
            return [receive_path / (tarball + ".md5")]

        def mock_results_push(ctrl: str, tb: Path, token: str) -> None:
            assert (
                tb == good_tb
            ), f"Unexpected tar ball, {tb!r} in mocked results_push function"
            raise RuntimeError(expected_error_msg)

        expected_result = Results(nstatus="", ntotal=1, ntbs=0, nerr=1)
        expected_error_msg = (
            f"Cannot connect to 'https://pbench.example.com/v2/1/upload/{tarball}'"
        )
        mappings = {
            "pbench-server": {
                "pbench-receive-dir-prefix": TestProcessTb.receive_dir,
                "put-token": "Authorization-token",
            }
        }
        monkeypatch.setattr(Path, "is_dir", mock_is_dir)
        monkeypatch.setattr(Path, "glob", mock_glob)
        monkeypatch.setattr(ProcessTb, "_results_push", mock_results_push)
        ptb = ProcessTb(MockConfig(mappings), logger)
        res = ptb.process_tb()

        assert res == expected_result
        assert expected_error_msg in caplog.text

    def test_process_tb(self, monkeypatch, logger):
        """verify processing of tar balls without any failure"""
        receive_path = Path(TestProcessTb.receive_dir + "-002")
        tarball = "log.tar.xz"
        good_tb = receive_path / tarball

        def mock_is_dir(self) -> bool:
            assert self == receive_path, f"Unexpected Results directory: {str(self)!r}"
            return True

        def mock_glob(self: Path, pattern: str) -> List[Path]:
            assert self == receive_path and pattern == "**/*.tar.xz.md5"
            return [receive_path / (tarball + ".md5")]

        def mock_results_push(ctrl: str, tb: Path, token: str) -> None:
            assert (
                tb == good_tb
            ), f"Unexpected tar ball, {tb!r} in mocked results_push function"
            return

        def mock_remove(path, *, dir_fd=None):
            assert path in [
                good_tb,
                Path(str(good_tb) + ".md5"),
            ], f"Unexpected tar ball, {path!r} in mocked os.remove()"

        expected_result = Results(
            nstatus=f": processed {tarball}\n", ntotal=1, ntbs=1, nerr=0
        )
        mappings = {
            "pbench-server": {
                "pbench-receive-dir-prefix": TestProcessTb.receive_dir,
                "put-token": "Authorization-token",
            }
        }
        monkeypatch.setattr(Path, "is_dir", mock_is_dir)
        monkeypatch.setattr(Path, "glob", mock_glob)
        monkeypatch.setattr(ProcessTb, "_results_push", mock_results_push)
        monkeypatch.setattr(os, "remove", mock_remove)
        ptb = ProcessTb(MockConfig(mappings), logger)
        res = ptb.process_tb()

        assert res == expected_result

    def test_process_tb_zero(self, monkeypatch, logger):
        """verify processing if there are no TBs without any failure"""
        receive_path = Path(TestProcessTb.receive_dir + "-002")

        def mock_is_dir(self) -> bool:
            assert self == receive_path, f"Unexpected Results directory: {str(self)!r}"
            return True

        def mock_glob(self: Path, pattern: str) -> List[Path]:
            assert self == receive_path and pattern == "**/*.tar.xz.md5"
            return []

        def mock_results_push(ctrl: str, tb: Path, token: str) -> None:
            assert False, "Unexpected call to mocked result_push function"

        expected_result = Results(nstatus="", ntotal=0, ntbs=0, nerr=0)
        mappings = {
            "pbench-server": {
                "pbench-receive-dir-prefix": TestProcessTb.receive_dir,
                "put-token": "Authorization-token",
            }
        }
        monkeypatch.setattr(Path, "is_dir", mock_is_dir)
        monkeypatch.setattr(Path, "glob", mock_glob)
        monkeypatch.setattr(ProcessTb, "_results_push", mock_results_push)
        ptb = ProcessTb(MockConfig(mappings), logger)
        res = ptb.process_tb()

        assert res == expected_result

    def test_multiple_process_tb(self, monkeypatch, caplog, logger):
        """verify tar balls processing at the time of Failure as well as success"""
        receive_path = Path(TestProcessTb.receive_dir + "-002")
        tarball = "log.tar.xz"
        bad_tarball = "bad_log.tar.xz"
        good_tb = receive_path / tarball
        bad_tb = receive_path / bad_tarball

        def mock_is_dir(self) -> bool:
            assert self == receive_path, f"Unexpected Results directory: {str(self)!r}"
            return True

        def mock_glob(self: Path, pattern: str) -> List[Path]:
            assert self == receive_path and pattern == "**/*.tar.xz.md5"
            return [
                receive_path / (bad_tarball + ".md5"),
                receive_path / (tarball + ".md5"),
            ]

        def mock_results_push(ctrl: str, tb: Path, token: str) -> None:
            if tb == bad_tb:
                raise FileNotFoundError(f"No such file or directory: '{tb.name}'")
            return

        def mock_remove(path, *, dir_fd=None):
            assert path in [
                good_tb,
                Path(str(good_tb) + ".md5"),
            ], f"Unexpected tar ball, {path!r} in mocked os.remove()"

        expected_result = Results(
            nstatus=f": processed {tarball}\n", ntotal=2, ntbs=1, nerr=1
        )
        mappings = {
            "pbench-server": {
                "pbench-receive-dir-prefix": TestProcessTb.receive_dir,
                "put-token": "Authorization-token",
            }
        }
        expected_error_msg = f"No such file or directory: '{bad_tarball}'"
        monkeypatch.setattr(Path, "is_dir", mock_is_dir)
        monkeypatch.setattr(Path, "glob", mock_glob)
        monkeypatch.setattr(ProcessTb, "_results_push", mock_results_push)
        monkeypatch.setattr(os, "remove", mock_remove)
        caplog.set_level(logging.ERROR, logger=logger.name)
        ptb = ProcessTb(MockConfig(mappings), logger)
        res = ptb.process_tb()

        assert res == expected_result
        assert expected_error_msg in caplog.text
