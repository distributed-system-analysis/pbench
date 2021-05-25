import logging
import pytest

from pathlib import Path

from pbench_server_put_shim_001 import get_receive_dir, process_tb, Results
from pbench.common.logger import get_pbench_logger
from pbench.common.results import CopyResultTb
from pbench.test.unit.server.common import tarball, bad_tarball


class FileUploadError(Exception):
    pass


class TestProcessTb:
    @pytest.fixture(autouse=True)
    def config_and_logger(self, valid_config):
        # Setup the configuration and logger
        self.config = valid_config
        self.logger = get_pbench_logger("pbench", valid_config)
        self.tbname = Path(tarball).name

        yield
        # Teardown the setup
        self.config, self.logger = None, None

    def test_get_receive_dir(self):
        """verify the pbench-receive-dir-prefix directory"""
        res = get_receive_dir(self.config, self.logger)
        expected_path = "/srv/pbench/pbench-move-results-receive/fs-version-002"

        assert str(res).endswith(expected_path)

    def test_get_receive_dir_failed(self, invalid_config, caplog):
        """verify the pbench-receive-dir-prefix directory.

        Note: Checking logs to look for any failure"""

        res = get_receive_dir(invalid_config, self.logger)
        expected_error_msg = "Failed: No value for config option pbench-receive-dir-prefix in section pbench-server"

        assert res is None
        assert expected_error_msg in caplog.text

    def test_get_receive_dir_value_failed(self, invalid_value_config, caplog):
        res = get_receive_dir(invalid_value_config, self.logger)
        prefix = invalid_value_config.get("pbench-server", "pbench-receive-dir-prefix")
        expected_error_msg = str(
            f"Failed: {prefix}-002 does not exist, or is not a directory"
        )

        assert res is None
        assert expected_error_msg in caplog.text

    def test_process_tb_file_not_found_error(self, caplog):
        """checks normal processing when tar ball is not present"""

        receive_dir = "server/bin/test/fixtures/upload/bad_tarball"
        expected_result = Results(nstatus="", ntotal=1, ntbs=0)
        expected_error_msg = f"No such file or directory: '{receive_dir}/{bad_tarball}'"
        res = process_tb(self.config, self.logger, receive_dir)

        assert res == expected_result
        assert expected_error_msg in caplog.text

    def test_process_tb_connection_error(self, copy_tb, monkeypatch, caplog):
        """checks normal processing when Connection Error is faced"""

        def mock_copy_result_tb(self, token):
            raise RuntimeError(f"Cannot connect to '{self.upload_url}'")

        receive_dir = "server/bin/test/fixtures/upload/tarball"
        expected_result = Results(nstatus="", ntotal=1, ntbs=0)
        expected_error_msg = (
            f"Cannot connect to 'https://pbench.example.com/v2/1/upload/{self.tbname}'"
        )
        monkeypatch.setattr(CopyResultTb, "copy_result_tb", mock_copy_result_tb)
        res = process_tb(self.config, self.logger, receive_dir)

        assert res == expected_result
        assert expected_error_msg in caplog.text

    def test_process_tb(self, monkeypatch):
        """verify processing of tar balls without any failure"""

        def mock_copy_result_tb(self, token):
            return

        receive_dir = "server/bin/test/fixtures/upload/tarball"
        expected_result = Results(
            nstatus=f": processed {receive_dir}/{self.tbname}\n", ntotal=1, ntbs=1
        )
        monkeypatch.setattr(CopyResultTb, "copy_result_tb", mock_copy_result_tb)
        res = process_tb(self.config, self.logger, receive_dir)

        assert res == expected_result

    def test_process_tb_zero(self):
        """verify processing if there are no TBs without any failure"""

        receive_dir = "server/bin/test/fixtures/upload/tarball"
        expected_result = Results(nstatus="", ntotal=0, ntbs=0)
        res = process_tb(self.config, self.logger, receive_dir)

        assert res == expected_result

    def test_multiple_process_tb(self, copy_tb, monkeypatch, caplog):
        """verify tar balls processing at the time of Failure as well as success"""

        def mock_copy_result_tb(self, token):
            return

        receive_dir = "server/bin/test/fixtures/upload"
        expected_result = Results(
            nstatus=f": processed {receive_dir}/tarball/{self.tbname}\n",
            ntotal=2,
            ntbs=1,
        )
        expected_error_msg = (
            f"No such file or directory: '{receive_dir}/bad_tarball/{bad_tarball}'"
        )
        monkeypatch.setattr(CopyResultTb, "copy_result_tb", mock_copy_result_tb)
        caplog.set_level(logging.ERROR, logger=self.logger.name)
        res = process_tb(self.config, self.logger, receive_dir)

        assert res == expected_result
        assert expected_error_msg in caplog.text
