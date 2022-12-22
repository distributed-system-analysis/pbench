from http import HTTPStatus
import logging
import os
from pathlib import Path

import pytest
import responses

from pbench.agent import PbenchAgentConfig
from pbench.agent.results import CopyResultTb
from pbench.test.unit.agent.task.common import bad_tarball, tarball


class TestCopyResults:
    @pytest.fixture(autouse=True)
    def config(self):
        # Setup the configuration
        self.config = PbenchAgentConfig(os.environ["_PBENCH_AGENT_CONFIG"])
        yield
        # Teardown the setup
        self.config = None

    @responses.activate
    def test_copy_tar(self, agent_logger):
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
            agent_logger,
        )
        crt.copy_result_tb("token", "access")

    @responses.activate
    def test_bad_tar(self, caplog, agent_logger):
        responses.add(
            responses.PUT,
            f"http://pbench.example.com/api/v1/upload/{bad_tarball}",
            status=HTTPStatus.OK,
        )
        expected_error_message = f"Tar ball '{bad_tarball}' does not exist"
        caplog.set_level(logging.ERROR, logger=agent_logger.name)
        with pytest.raises(FileNotFoundError) as excinfo:
            crt = CopyResultTb(
                "controller",
                bad_tarball,
                0,
                "ignoremd5",
                self.config,
                agent_logger,
            )
            crt.copy_result_tb("token")
        assert str(excinfo.value).endswith(
            expected_error_message
        ), f"expected='...{expected_error_message}', found='{str(excinfo.value)}'"
