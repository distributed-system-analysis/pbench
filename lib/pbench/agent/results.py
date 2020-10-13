import datetime
import hashlib
import os
import sys
import tarfile
import errno
from pathlib import Path

import requests
from werkzeug.utils import secure_filename

from pbench.cli.agent.commands.log import add_metalog_option
from pbench.common import configtools


class MakeResultTb:
    def __init__(self, result_dir, target_dir, user, prefix, config, logger):
        assert (
            config and logger
        ), f"config, '{config!r}', and/or logger, '{logger!r}', not provided"
        if not result_dir:
            logger.error("Result directory not provided")
            sys.exit(1)
        if not target_dir:
            logger.error("Target directory not provided")
            sys.exit(1)
        try:
            self.result_dir = Path(result_dir).resolve(strict=True)
        except FileNotFoundError:
            logger.error("Invalid result directory provided: {}", result_dir)
            sys.exit(1)
        else:
            if not self.result_dir.is_dir():
                logger.error("Invalid result directory provided: {}", result_dir)
                sys.exit(1)
        try:
            self.target_dir = Path(target_dir).resolve(strict=True)
        except FileNotFoundError:
            logger.error("Invalid target directory provided: {}", target_dir)
            sys.exit(1)
        else:
            if not self.target_dir.is_dir():
                logger.error("Invalid target directory provided: {}", target_dir)
                sys.exit(1)
        self.user = user
        self.prefix = prefix
        self.config = config
        self.logger = logger

    def make_result_tb(self):
        if os.path.exists(f"{self.result_dir}.copied"):
            self.logger.debug("Already copied {}", self.result_dir)
            sys.exit(0)

        pbench_run_name = self.result_dir.name
        if os.path.exists(f"{self.result_dir}/.running"):
            self.logger.debug(
                "The benchmark is still running in {} - skipping; if that is"
                " not true, rmdir {}/.running, and try again",
                pbench_run_name,
                pbench_run_name,
            )
            sys.exit(0)

        try:
            md_log = Path(self.result_dir, "metadata.log").resolve(strict=True)
        except FileNotFoundError:
            self.logger.debug(
                "The {}/metadata.log file seems to be missing", pbench_run_name
            )
            sys.exit(0)

        opts, _ = configtools.parse_args()
        opts.filename = md_log
        conf_md, _ = configtools.init(opts, None)
        md_config = conf_md["pbench"]
        res_name = md_config.get("name")
        if res_name != pbench_run_name:
            self.logger.warning(
                "The run in directory {}"
                " has an unexpected metadata name, '{}' - skipping",
                self.config.pbench_run / pbench_run_name,
                res_name,
            )
            sys.exit(1)

        if self.user:
            add_metalog_option(md_log, "run", "user", self.user)

        if self.prefix:
            add_metalog_option(md_log, "run", "prefix", self.prefix)

        result_size = sum(f.stat().st_size for f in self.result_dir.rglob("*"))
        self.logger.debug(
            "preparing to tar up {} bytes of data from {}", result_size, self.result_dir
        )
        add_metalog_option(md_log, "run", "raw_size", f"{result_size}")

        timestamp = datetime.datetime.isoformat(datetime.datetime.now())
        add_metalog_option(
            md_log, "pbench", "tar-ball-creation-timestamp", f"{timestamp}"
        )

        tarball = self.target_dir / f"{pbench_run_name}.tar.xz"
        try:
            with tarfile.open(tarball, mode="x:xz") as tar:
                for f in self.result_dir.rglob("*"):
                    tar.add(os.path.realpath(f))
        except tarfile.TarError:
            self.logger.error(
                "tar ball creation failed for {}, skipping", self.result_dir
            )
            try:
                tarball.unlink()
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    self.logger.error("error removing failed tar ball, {}", tarball)
            sys.exit(1)

        self.make_md5sum(tarball)

        # The contract with the caller is to just return the full path to the
        # created tar ball.
        return str(tarball)

    def make_md5sum(self, tarball):
        tarball_md5 = Path(f"{tarball}.md5")
        try:
            hash_md5 = hashlib.md5()
            with tarball.open("rb") as tar:
                for chunk in iter(lambda: tar.read(4096), b""):
                    hash_md5.update(chunk)

            with tarball_md5.open("w") as md5:
                md5.write(f"{tarball.name} {hash_md5.hexdigest()}\n")
        except Exception:
            self.logger.error("md5sum failed for {}, skipping", tarball)
            try:
                tarball.unlink()
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    self.logger.error("error removing failed tar ball, {}", tarball)
            try:
                tarball_md5.unlink()
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    self.logger.error(
                        "error removing failed tar ball MD5, {}", tarball_md5
                    )
            sys.exit(1)


class CopyResultTb:
    chunk_size = 4096

    def __init__(self, controller, tarball, config, logger):
        if not os.path.exists(tarball):
            logger.error("tarball does not exist, '{}'", tarball)
            sys.exit(1)
        tarball_md5 = f"{tarball}.md5"
        if not os.path.exists(tarball_md5):
            logger.error("tarball's .md5 does not exist, '{}'", tarball_md5)
            sys.exit(1)
        self.tarball = Path(tarball)
        self.tarball_md5 = Path(tarball_md5)
        self.logger = logger
        server_rest_url = config.results.get("server_rest_url")
        self.upload_url = f"{server_rest_url}/upload/ctrl/{controller}"

    def read_in_chunks(self, file_object):
        data = file_object.read(self.chunk_size)
        while data:
            yield data
            data = file_object.read(self.chunk_size)

    def copy_result_tb(self):
        files = [f for f in self.tarball.parent.iterdir() if f.is_file()]
        file_count = len(files)
        if file_count != 2:
            self.logger.error(
                "(internal): unexpected file count, {}, associated with tarball, '{}'",
                file_count,
                self.tarball,
            )
            sys.exit(1)

        with open(self.tarball_md5, "r") as md5fp:
            md5sum = md5fp.read()
        filename = secure_filename(str(self.tarball))
        headers = {"filename": filename, "Content-MD5": md5sum}
        with self.tarball.open("rb") as f:
            try:
                response = requests.put(
                    self.upload_url, data=self.read_in_chunks(f), headers=headers
                )
                self.logger.info("File uploaded successfully")
            except Exception:
                self.logger.exception("There was something wrong with your request")
                sys.exit(1)
        if not response.status_code == 200:
            self.logger.error(
                "There was something wrong with your request, error code: '{}'",
                response.status_code,
            )
            sys.exit(1)
