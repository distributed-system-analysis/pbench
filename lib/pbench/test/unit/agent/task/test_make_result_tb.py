import datetime
import logging
import os
import tarfile
import tempfile
from pathlib import Path

import pytest

from pbench.agent import PbenchAgentConfig
from pbench.agent.results import MakeResultTb
from pbench.common import MetadataLog
from pbench.common.logger import get_pbench_logger
from pbench.common.utils import md5sum
from pbench.test.unit.agent.task.common import MockDatetime


class TestMakeResultTb:
    @pytest.fixture(autouse=True)
    def config_and_logger(self, valid_config):
        with tempfile.TemporaryDirectory() as target_dir, tempfile.TemporaryDirectory() as run_dir:
            # Setup the configuration and logger
            self.controller = "controller-42.example.com"
            self.target_dir = Path(target_dir)
            self.config = PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"])
            self.logger = get_pbench_logger("pbench", self.config)

            script, config, date = "bm", "config-00", "1970.01.01T00.00.42"
            self.name = f"{script}_{config}_{date}"
            self.result_dir = Path(run_dir) / self.name
            self.result_dir.mkdir()
            mdlog_name = self.result_dir / "metadata.log"

            mdlog = MetadataLog()
            mdlog.add_section("pbench")
            mdlog.set("pbench", "config", config)
            mdlog.set("pbench", "date", date)
            mdlog.set("pbench", "script", script)
            mdlog.set("pbench", "name", self.name)
            mdlog.add_section("run")
            mdlog.set("run", "controller", "localhost")
            mdlog.set("run", "start_run", "1970.01.01T00.00.40")
            mdlog.set("run", "end_run", "1970.01.01T00.00.41")
            with mdlog_name.open("w") as fp:
                mdlog.write(fp)

            yield

            # Teardown the setup
            (
                self.controller,
                self.name,
                self.result_dir,
                self.target_dir,
                self.config,
                self.logger,
            ) = (
                None,
                None,
                None,
                None,
                None,
                None,
            )

    @pytest.mark.parametrize("result_dir", ("bad/bad/result/dir", ""))
    def test_bad_result_dir(self, result_dir, caplog):
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        with pytest.raises(FileNotFoundError):
            mrt = MakeResultTb(
                result_dir, self.target_dir, self.controller, self.config, self.logger
            )
            mrt.make_result_tb()

    @pytest.mark.parametrize("target_dir", ("bad/bad/target/dir", ""))
    def test_bad_target_dir(self, target_dir, caplog):
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        with pytest.raises(FileNotFoundError):
            mrt = MakeResultTb(
                self.result_dir, target_dir, self.controller, self.config, self.logger
            )
            mrt.make_result_tb()

    def test_already_copied(self, caplog):
        caplog.set_level(logging.DEBUG, logger=self.logger.name)
        full_result_dir = self.result_dir.resolve(strict=True)
        expected_error_message = f"Already copied {full_result_dir.name}"
        with open(f"{full_result_dir}.copied", "x"):
            with pytest.raises(Exception) as e:
                mrt = MakeResultTb(
                    self.result_dir,
                    self.target_dir,
                    self.controller,
                    self.config,
                    self.logger,
                )
                mrt.make_result_tb()
            assert str(e).endswith(
                expected_error_message
            ), f"Unexpected error: '{e}', expecting: '{expected_error_message}'"

    def test_running(self, caplog):
        caplog.set_level(logging.DEBUG, logger=self.logger.name)
        expected_error_message = (
            f"The benchmark is still running in {self.result_dir.name} - skipping;"
            f" if that is not true, rmdir {self.result_dir.name}/.running, and try again"
        )
        full_result_dir = self.result_dir.resolve(strict=True)
        with open(f"{full_result_dir}/.running", "x"):
            with pytest.raises(RuntimeError) as e:
                mrt = MakeResultTb(
                    self.result_dir,
                    self.target_dir,
                    self.controller,
                    self.config,
                    self.logger,
                )
                mrt.make_result_tb()
            assert str(e).endswith(
                expected_error_message
            ), f"Unexpected error: '{e}', expecting: '{expected_error_message}'"

    def test_make_tb(self, monkeypatch):
        monkeypatch.setattr(datetime, "datetime", MockDatetime)
        expected_tb = self.target_dir / f"{self.name}.tar.xz"
        mrt = MakeResultTb(
            self.result_dir, self.target_dir, self.controller, self.config, self.logger
        )
        tarball, tarball_len, tarball_md5 = mrt.make_result_tb()
        assert tarball.samefile(expected_tb), f"{tarball} {expected_tb}"
        assert tarball.exists()
        assert tarball.stat().st_size == tarball_len and tarball_len > 0
        calc_len, calc_md5 = md5sum(str(tarball))
        assert tarball_len == calc_len
        assert calc_md5 == tarball_md5
        with tarfile.open(str(tarball), "r:xz") as tf:
            for tf_entry in tf:
                assert tf_entry.name.startswith(
                    self.name
                ), f"tar ball entry does not start with {self.name}, '{tf_entry.name}'"
