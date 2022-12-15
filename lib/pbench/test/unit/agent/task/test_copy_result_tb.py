from http import HTTPStatus
import logging
import os
from pathlib import Path

import pytest
import responses

from pbench.agent import PbenchAgentConfig
from pbench.agent.results import CopyResultTb
from pbench.common.logger import get_pbench_logger
from pbench.test.unit.agent.task.common import bad_tarball, tarball


class TestCopyResults:
    @pytest.fixture(autouse=True)
    def config_and_logger(self):
        # Setup the configuration and logger
        self.config = PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"])
        self.logger = get_pbench_logger("pbench", self.config)
        yield
        # Teardown the setup
        self.config, self.logger = None, None

    @responses.activate
    def test_copy_tar(self):
        tbname = Path(tarball)
        responses.add(
            responses.PUT,
            f"http://pbench.example.com/api/v1/upload/{tbname.name}",
            status=HTTPStatus.OK,
        )
        crt = CopyResultTb(
            "controller",
            tbname,
            tbname.stat().st_size,
            "someMD5",
            self.config,
            self.logger,
        )
        crt.copy_result_tb("token", "access")

    @responses.activate
    def test_bad_tar(self, caplog):
        responses.add(
            responses.PUT,
            f"http://pbench.example.com/api/v1/upload/{bad_tarball}",
            status=HTTPStatus.OK,
        )
        expected_error_message = f"Tar ball '{bad_tarball}' does not exist"
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        with pytest.raises(FileNotFoundError) as excinfo:
            crt = CopyResultTb(
                "controller", bad_tarball, 0, "ignoremd5", self.config, self.logger
            )
            crt.copy_result_tb("token")
        assert str(excinfo.value).endswith(
            expected_error_message
        ), f"expected='...{expected_error_message}', found='{str(excinfo.value)}'"
