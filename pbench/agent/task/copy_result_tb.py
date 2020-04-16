import os
import sys
from pathlib import Path

import requests

from werkzeug.utils import secure_filename

from pbench.agent import logger
from pbench.agent.config import AgentConfig


class CopyResultTb:
    def __init__(self, tarball, path, _logger=None):
        config = AgentConfig()
        server_rest_url = config.results.get("server_rest_url")

        self.tarball = tarball
        self.path = path
        self.chunk_size = 4096
        self.logger = logger if not _logger else _logger
        self.upload_url = f"{server_rest_url}/upload"
        self.controller_dir = os.path.dirname(self.tarball)
        self.controller = os.path.basename(self.controller_dir)

    def read_in_chunks(self, file_object):
        while True:
            data = file_object.read(self.chunk_size)
            if not data:
                break
            yield data

    def post_file(self, file):
        filename = secure_filename(os.path.join(self.path, file))
        with open(f"{os.path.join(self.path, file)}.md5.check", "r") as _check:
            md5sum = _check.read()
        headers = {"filename": filename, "md5sum": md5sum}
        content_path = os.path.abspath(file)
        with open(content_path, "rb") as f:
            try:
                response = requests.post(
                    self.upload_url, data=self.read_in_chunks(f), headers=headers
                )
                self.logger.info("File uploaded successfully")
            except Exception:
                self.logger.exception("There was something wrong with your request")
                sys.exit(1)
        if not response.status_code == 200:
            self.logger.error("There was something wrong with your request")
            self.logger.error("Error code: %s" % response.status_code)
            sys.exit(1)

    def copy_result_tb(self):
        if not os.path.exists(self.tarball):
            self.logger.error("tarball does not exist, %s" % self.tarball)
            sys.exit(1)
        if not os.path.exists(f"{self.tarball}.md5.check"):
            self.logger.error(
                "tarball's .md5.check does not exist, %s.md5.check" % self.tarball
            )
            sys.exit(1)

        files = [file for file in Path(self.controller_dir).iterdir() if file.is_file()]
        file_count = len(files)
        if file_count != 2:
            self.logger.error(
                "(internal): unexpected file count, %s, associated with tarball, %s"
                % (file_count, self.tarball)
            )
            sys.exit(1)

        self.post_file(self.tarball)
