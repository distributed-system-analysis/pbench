import datetime
import logging
import os

import pytest

from pbench.lib.agent.make_result_tb import MakeResultTb
from pbench.test.unit.agent.common import MockDatetime, target_dir, MRT_DIR


class TestMakeResultTb:
    logger = logging.getLogger()

    @pytest.fixture(autouse=True)
    def teardown(self):
        if os.path.exists(f"{os.path.realpath(MRT_DIR)}.copied"):
            os.remove(f"{os.path.realpath(MRT_DIR)}.copied")
        if os.path.exists(f"{os.path.realpath(MRT_DIR)}/.running"):
            os.remove(f"{os.path.realpath(MRT_DIR)}/.running")

    @pytest.mark.parametrize("result_dir", ("bad/bad/result/dir", ""))
    def test_bad_result_dir(self, result_dir, caplog):
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        expected_error_message = "Invalid result directory provided: %s" % result_dir
        try:
            mrt = MakeResultTb(
                result_dir, target_dir, "pbench", "", _logger=self.logger
            )
            mrt.make_result_tb()
        except SystemExit:
            assert caplog.records
            assert caplog.records[0].msg == expected_error_message
        else:
            assert False

    @pytest.mark.parametrize("target_dir", ("bad/bad/result/dir", ""))
    def test_bad_target_dir(self, target_dir, caplog):
        logger = logging.getLogger()
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        expected_error_message = "Invalid target directory provided: %s" % target_dir
        try:
            mrt = MakeResultTb(MRT_DIR, target_dir, "pbench", "", _logger=logger)
            mrt.make_result_tb()
        except SystemExit:
            assert caplog.records
            assert caplog.records[0].msg == expected_error_message
        else:
            assert False

    def test_already_copied(self, caplog):
        caplog.set_level(logging.DEBUG, logger=self.logger.name)
        first_expected_error_message = (
            f"The benchmark is still running in {os.path.basename(MRT_DIR)} - skipping"
        )
        second_expected_error_message = f"If that is not true, rmdir {os.path.basename(MRT_DIR)}/.running, and try again"
        full_result_dir = os.path.realpath(MRT_DIR)
        with open(f"{full_result_dir}/.running", "x"):
            try:
                mrt = MakeResultTb(
                    MRT_DIR, target_dir, "pbench", "", _logger=self.logger
                )
                mrt.make_result_tb()
            except SystemExit:
                assert caplog.records
                assert caplog.records[0].msg == first_expected_error_message
                assert caplog.records[1].msg == second_expected_error_message
            else:
                assert False

    def test_running(self, caplog):
        caplog.set_level(logging.DEBUG, logger=self.logger.name)
        expected_error_message = "Already copied %s" % MRT_DIR
        full_result_dir = os.path.realpath(MRT_DIR)
        with open(f"{full_result_dir}.copied", "x"):
            try:
                mrt = MakeResultTb(
                    MRT_DIR, target_dir, "pbench", "", _logger=self.logger
                )
                mrt.make_result_tb()
            except SystemExit:
                assert caplog.records
                assert caplog.records[0].msg == expected_error_message
            else:
                assert False

    @staticmethod
    def test_make_tb(monkeypatch):
        monkeypatch.setattr(datetime, "datetime", MockDatetime)
        try:
            mrt = MakeResultTb(MRT_DIR, target_dir, "pbench", "")
            tarball = mrt.make_result_tb()
        except SystemExit:
            assert False
        assert tarball == os.path.join(target_dir, "make_result_tb.tar.xz")
        assert os.path.exists(tarball)
