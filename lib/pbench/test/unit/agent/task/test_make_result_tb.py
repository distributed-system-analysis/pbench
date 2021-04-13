import datetime
import logging
import os
import tempfile
from pathlib import Path

import pytest

from pbench.agent import PbenchAgentConfig
from pbench.agent.results import MakeResultTb
from pbench.common.logger import get_pbench_logger
from pbench.test.unit.agent.task.common import MockDatetime, MRT_DIR


class TestMakeResultTb:
    @pytest.fixture(autouse=True)
    def config_and_logger(self, valid_config):
        with tempfile.TemporaryDirectory() as target_dir:
            # Setup the configuration and logger
            self.target_dir = target_dir
            self.config = PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"])
            self.logger = get_pbench_logger("pbench", self.config)
            yield
            # Teardown the setup
            self.config, self.logger = None, None
            if os.path.exists(f"{os.path.realpath(MRT_DIR)}.copied"):
                os.remove(f"{os.path.realpath(MRT_DIR)}.copied")
            if os.path.exists(f"{os.path.realpath(MRT_DIR)}/.running"):
                os.remove(f"{os.path.realpath(MRT_DIR)}/.running")

    @pytest.mark.parametrize("result_dir", ("bad/bad/result/dir", ""))
    def test_bad_result_dir(self, result_dir, caplog):
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        with pytest.raises(FileNotFoundError):
            mrt = MakeResultTb(result_dir, self.target_dir, self.config, self.logger)
            mrt.make_result_tb()

    @pytest.mark.parametrize("target_dir", ("bad/bad/target/dir", ""))
    def test_bad_target_dir(self, target_dir, caplog):
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        with pytest.raises(FileNotFoundError):
            mrt = MakeResultTb(MRT_DIR, target_dir, self.config, self.logger)
            mrt.make_result_tb()

    def test_already_copied(self, caplog):
        caplog.set_level(logging.DEBUG, logger=self.logger.name)
        full_result_dir = os.path.realpath(MRT_DIR)
        expected_error_message = f"Already copied {full_result_dir}"
        with open(f"{full_result_dir}.copied", "x"):
            with pytest.raises(Exception) as e:
                mrt = MakeResultTb(MRT_DIR, self.target_dir, self.config, self.logger)
                mrt.make_result_tb()
            assert str(e).endswith(expected_error_message)

    def test_running(self, caplog):
        caplog.set_level(logging.DEBUG, logger=self.logger.name)
        expected_error_message = (
            f"The benchmark is still running in {os.path.basename(MRT_DIR)} - skipping;"
            f" if that is not true, rmdir {os.path.basename(MRT_DIR)}/.running, and try again"
        )
        full_result_dir = os.path.realpath(MRT_DIR)
        with open(f"{full_result_dir}/.running", "x"):
            with pytest.raises(RuntimeError) as e:
                mrt = MakeResultTb(MRT_DIR, self.target_dir, self.config, self.logger)
                mrt.make_result_tb()
            assert str(e).endswith(expected_error_message)

    def test_make_tb(self, monkeypatch):
        monkeypatch.setattr(datetime, "datetime", MockDatetime)
        mrt = MakeResultTb(MRT_DIR, self.target_dir, self.config, self.logger)
        tarball = mrt.make_result_tb()
        expected_tb = os.path.join(self.target_dir, "make_result_tb.tar.xz")
        assert Path(tarball).samefile(expected_tb)
        assert os.path.exists(tarball)
