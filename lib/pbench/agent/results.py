import datetime
import hashlib
import os
import re
import sys
import tarfile
from pathlib import Path

import requests
from werkzeug.utils import secure_filename

from pbench.agent.logger import logger
from pbench.agent.config import AgentConfig
from pbench.agent import fs
from pbench.cli.agent.commands.log import add_metalog_option
from pbench.common import configtools


class Results:
    def __init__(self):
        self.config = AgentConfig()

    def clear(self):
        for path in Path(self.config.rundir).glob("*"):
            if not re.search(r"(tmp|tools)", str(path.name)):
                fs.removedir(path)


class MakeResultTb:
    def __init__(self, result_dir, target_dir, user, prefix, _logger=None):
        self.result_dir = result_dir
        self.target_dir = target_dir
        self.user = user
        self.prefix = prefix
        self.logger = logger if not _logger else _logger

    def make_result_tb(self):
        config = AgentConfig()

        if not os.path.exists(self.result_dir):
            self.logger.error("Invalid result directory provided: %s" % self.result_dir)
            sys.exit(1)

        if not os.path.exists(self.target_dir):
            self.logger.error("Invalid target directory provided: %s" % self.target_dir)
            sys.exit(1)

        full_result_dir = os.path.realpath(self.result_dir)
        pbench_run_name = os.path.basename(self.result_dir)
        if os.path.exists(f"{full_result_dir}.copied"):
            self.logger.debug("Already copied %s" % self.result_dir)
            sys.exit(0)

        if os.path.exists(f"{full_result_dir}/.running"):
            self.logger.debug(
                "The benchmark is still running in %s - skipping" % pbench_run_name
            )
            self.logger.debug(
                "If that is not true, rmdir %s/.running, and try again"
                % pbench_run_name
            )
            sys.exit(0)

        md_log = f"{full_result_dir}/metadata.log"
        if not os.path.exists(md_log):
            self.logger.debug(
                "The %s/metadata.log file seems to be missing", pbench_run_name
            )
            sys.exit(0)

        opts, _ = configtools.parse_args()
        opts.filename = md_log
        conf_md, _ = configtools.init(opts, None)
        md_config = conf_md["pbench"]
        res_name = md_config.get("name")
        pbench_run = config.agent.get("pbench_run")
        if res_name != pbench_run_name:
            self.logger.warning(
                "The run in directory %s/%s "
                "has an unexpected metadata name, '%s' - skipping"
                % (pbench_run, pbench_run_name, res_name)
            )
            sys.exit(1)

        if self.user:
            add_metalog_option(md_log, "run", "user", self.user)

        if self.prefix:
            add_metalog_option(md_log, "run", "prefix", self.prefix)

        result_size = sum(
            file.stat().st_size for file in Path(full_result_dir).rglob("*")
        )
        self.logger.debug(
            "preparing to tar up %s bytes of data from %s"
            % (result_size, full_result_dir)
        )
        add_metalog_option(md_log, "run", "raw_size", f"{result_size}")

        timestamp = datetime.datetime.isoformat(datetime.datetime.now())
        add_metalog_option(
            md_log, "pbench", "tar-ball-creation-timestamp", f"{timestamp}"
        )

        tarball = os.path.join(self.target_dir, f"{pbench_run_name}.tar.xz")
        files = [os.path.realpath(file) for file in Path(full_result_dir).rglob("*")]
        try:
            with tarfile.open(tarball, mode="x:xz") as tar:
                for f in files:
                    tar.add(f)
        except tarfile.TarError:
            self.logger.error(
                "tar ball creation failed for %s, skipping" % self.result_dir
            )
            if os.path.exists(tarball):
                os.remove(tarball)
            sys.exit(1)

        self.make_md5sum(tarball)

        return tarball

    def make_md5sum(self, tarball):
        tarball_md5 = f"{tarball}.md5.check"
        try:
            hash_md5 = hashlib.md5()
            with open(tarball, "rb") as tar:
                for chunk in iter(lambda: tar.read(4096), b""):
                    hash_md5.update(chunk)

            with open(tarball_md5, "w") as md5:
                md5.write(hash_md5.hexdigest())
        except Exception:
            self.logger.error("md5sum failed for %s, skipping" % tarball)
            if os.path.exists(tarball):
                os.remove(tarball)
            if os.path.exists(tarball_md5):
                os.remove(tarball_md5)
            sys.exit(1)


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
