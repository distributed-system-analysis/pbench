import datetime
import logging
import os
import tempfile

import pytest

from pbench.agent import PbenchAgentConfig
from pbench.common.logger import get_pbench_logger
from pbench.agent.results import MakeResultTb
from pbench.test.unit.agent.task.common import MockDatetime, MRT_DIR


class TestMakeResultTb:
    @pytest.fixture(autouse=True)
    def config_and_logger(self):
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
        if result_dir:
            expected_error_message = f"Invalid result directory provided: {result_dir}"
        else:
            expected_error_message = "Result directory not provided"
        try:
            mrt = MakeResultTb(
                result_dir, self.target_dir, "pbench", "", self.config, self.logger
            )
            mrt.make_result_tb()
        except SystemExit:
            assert caplog.records
            assert len(caplog.records) == 1
            assert caplog.records[0].message == expected_error_message
        else:
            assert False

    @pytest.mark.parametrize("target_dir", ("bad/bad/target/dir", ""))
    def test_bad_target_dir(self, target_dir, caplog):
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        if target_dir:
            expected_error_message = f"Invalid target directory provided: {target_dir}"
        else:
            expected_error_message = "Target directory not provided"
        try:
            mrt = MakeResultTb(
                MRT_DIR, target_dir, "pbench", "", self.config, self.logger
            )
            mrt.make_result_tb()
        except SystemExit:
            assert caplog.records
            assert len(caplog.records) == 1
            assert caplog.records[0].message == expected_error_message
        else:
            assert False

    def test_already_copied(self, caplog):
        caplog.set_level(logging.DEBUG, logger=self.logger.name)
        expected_error_message = (
            f"The benchmark is still running in {os.path.basename(MRT_DIR)} - skipping;"
            f" if that is not true, rmdir {os.path.basename(MRT_DIR)}/.running, and try again"
        )
        full_result_dir = os.path.realpath(MRT_DIR)
        with open(f"{full_result_dir}/.running", "x"):
            try:
                mrt = MakeResultTb(
                    MRT_DIR, self.target_dir, "pbench", "", self.config, self.logger
                )
                mrt.make_result_tb()
            except SystemExit:
                assert caplog.records
                assert len(caplog.records) == 1
                assert caplog.records[0].message == expected_error_message
            else:
                assert False

    def test_running(self, caplog):
        caplog.set_level(logging.DEBUG, logger=self.logger.name)
        full_result_dir = os.path.realpath(MRT_DIR)
        expected_error_message = f"Already copied {full_result_dir}"
        with open(f"{full_result_dir}.copied", "x"):
            try:
                mrt = MakeResultTb(
                    MRT_DIR, self.target_dir, "pbench", "", self.config, self.logger
                )
                mrt.make_result_tb()
            except SystemExit:
                assert caplog.records
                assert caplog.records[0].message == expected_error_message
            else:
                assert False

    def test_make_tb(self, monkeypatch):
        monkeypatch.setattr(datetime, "datetime", MockDatetime)
        try:
            mrt = MakeResultTb(
                MRT_DIR, self.target_dir, "pbench", "", self.config, self.logger
            )
            tarball = mrt.make_result_tb()
        except SystemExit:
            assert False
        assert tarball == os.path.join(self.target_dir, "make_result_tb.tar.xz")
        assert os.path.exists(tarball)
