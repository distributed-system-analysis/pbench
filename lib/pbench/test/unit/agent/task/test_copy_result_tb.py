import logging
import os
from tempfile import NamedTemporaryFile

import pytest
import responses

from pbench.agent import PbenchAgentConfig
from pbench.common.logger import get_pbench_logger
from pbench.agent.results import CopyResultTb
from pbench.test.unit.agent.task.common import tarball, bad_tarball


class TestCopyResults:
    @pytest.fixture(autouse=True)
    def config_and_logger(self):
        # Setup the configuration and logger
        self.config = PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"])
        self.logger = get_pbench_logger("unittest", self.config)
        yield
        # Teardown the setup
        self.config, self.logger = None, None

    @responses.activate
    def test_copy_tar(self, valid_config):
        responses.add(
            responses.PUT,
            "http://pbench.example.com/api/v1/upload/ctrl/controller",
            status=200,
        )
        try:
            crt = CopyResultTb("controller", tarball, self.config, self.logger)
            crt.copy_result_tb()
        except SystemExit:
            assert False
        else:
            assert True

    @responses.activate
    def test_bad_tar(self, caplog, valid_config):
        responses.add(
            responses.PUT,
            "http://pbench.example.com/api/v1/upload/ctrl/controller",
            status=200,
        )
        expected_error_message = f"tarball does not exist, '{bad_tarball}'"
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        try:
            crt = CopyResultTb("controller", bad_tarball, self.config, self.logger)
            crt.copy_result_tb()
        except SystemExit:
            assert caplog.records
            assert len(caplog.records) == 1
            assert caplog.records[0].message == expected_error_message
        else:
            assert False

    @responses.activate
    def test_missing_md5(self, caplog, valid_config):
        responses.add(
            responses.PUT,
            "http://pbench.example.com/api/v1/upload/ctrl/controller",
            status=200,
        )
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        with NamedTemporaryFile(suffix=".tar.xz") as missing_md5_tar:
            expected_error_message = (
                f"tarball's .md5 does not exist, '{missing_md5_tar.name}.md5'"
            )
            try:
                crt = CopyResultTb(
                    "controller", missing_md5_tar.name, self.config, self.logger
                )
                crt.copy_result_tb()
            except SystemExit:
                assert caplog.records
                assert len(caplog.records) == 1
                assert caplog.records[0].message == expected_error_message
            else:
                assert False

    @responses.activate
    def test_multiple_files(self, caplog, valid_config):
        responses.add(
            responses.PUT,
            "http://pbench.example.com/api/v1/upload/ctrl/controller",
            status=200,
        )
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        base_dir = os.path.dirname(tarball)
        with NamedTemporaryFile(suffix=".add", dir=base_dir):
            expected_error_message = f"(internal): unexpected file count, 3, associated with tarball, '{tarball}'"
            try:
                crt = CopyResultTb("controller", tarball, self.config, self.logger)
                crt.copy_result_tb()
            except SystemExit:
                assert caplog.records
                assert len(caplog.records) == 1
                assert caplog.records[0].message == expected_error_message
            else:
                assert False
