import logging
import os
from tempfile import NamedTemporaryFile

import responses

from pbench.lib.agent.copy_result_tb import CopyResultTb
from pbench.test.unit.agent.common import tarball, bad_tarball


class TestCopyResults:
    logger = logging.getLogger()

    @staticmethod
    @responses.activate
    def test_copy_tar():
        responses.add(
            responses.POST, "http://pbench.example.com/api/v1/upload", status=200
        )
        try:
            crt = CopyResultTb(tarball, "")
            crt.copy_result_tb()
        except SystemExit:
            assert False
        assert True

    @responses.activate
    def test_bad_tar(self, caplog):
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        responses.add(
            responses.POST, "http://pbench.example.com/api/v1/upload", status=200
        )
        expected_error_message = "tarball does not exist, %s" % bad_tarball
        try:
            crt = CopyResultTb(bad_tarball, "", self.logger)
            crt.copy_result_tb()
        except SystemExit:
            assert caplog.records
            assert caplog.records[0].msg == expected_error_message
        else:
            assert False

    @responses.activate
    def test_missing_md5(self, caplog):
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        responses.add(
            responses.POST, "http://pbench.example.com/api/v1/upload", status=200
        )
        with NamedTemporaryFile(suffix=".tar.xz") as missing_md5_tar:
            expected_error_message = (
                "tarball's .md5.check does not exist, %s.md5.check"
                % missing_md5_tar.name
            )
            try:
                crt = CopyResultTb(missing_md5_tar.name, "", self.logger)
                crt.copy_result_tb()
            except SystemExit:
                assert caplog.records
                assert caplog.records[0].msg == expected_error_message
            else:
                assert False

    @responses.activate
    def test_multiple_files(self, caplog):
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        responses.add(
            responses.POST, "http://pbench.example.com/api/v1/upload", status=200
        )
        base_dir = os.path.dirname(tarball)
        with NamedTemporaryFile(suffix=".add", dir=base_dir):
            expected_error_message = (
                "(internal): unexpected file count, 3, associated with tarball, %s"
                % tarball
            )
            try:
                crt = CopyResultTb(tarball, "", self.logger)
                crt.copy_result_tb()
            except SystemExit:
                assert caplog.records
                assert caplog.records[0].msg == expected_error_message
            else:
                assert False
