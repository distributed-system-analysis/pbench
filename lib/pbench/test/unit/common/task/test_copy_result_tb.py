import os
import pytest
import responses

from http import HTTPStatus
from pathlib import Path

from pbench import PbenchConfig
from pbench.common.logger import get_pbench_logger
from pbench.common.results import CopyResultTb
from pbench.common.utils import md5sum
from pbench.test.unit.server.common import tarball, bad_tarball


class TestCopyResults:
    @pytest.fixture(autouse=True)
    def config_and_logger(self):
        # Setup the configuration and logger
        config_prefix_path = Path("lib/pbench/test/unit/common/config/")
        self.config = PbenchConfig(config_prefix_path / "pbench.cfg")
        self.logger = get_pbench_logger("pbench", self.config)
        yield
        # Teardown the setup
        self.config, self.logger = None, None

    @responses.activate
    def test_copy_tar(self):
        tbname = os.path.basename(tarball)
        upload_url = f"http://pbench.example.com/api/v1/upload/{tbname}"
        tblen, tbmd5 = md5sum(tarball)
        responses.add(
            responses.PUT,
            f"http://pbench.example.com/api/v1/upload/{tbname}",
            status=HTTPStatus.OK,
        )
        crt = CopyResultTb("controller", tarball, tblen, tbmd5, upload_url, self.logger)
        # Implicit assert in copy_result_tb, if the specified endpoint isn't called
        # it should fail
        crt.copy_result_tb("token")

    @responses.activate
    def test_bad_tar(self, caplog):
        responses.add(
            responses.PUT,
            f"http://pbench.example.com/api/v1/upload/{bad_tarball}",
            status=HTTPStatus.OK,
        )
        upload_url = f"http://pbench.example.com/api/v1/upload/{bad_tarball}"
        with pytest.raises(FileNotFoundError):
            tblen, tbmd5 = md5sum(bad_tarball)
            CopyResultTb(
                "controller", bad_tarball, tblen, tbmd5, upload_url, self.logger
            )
