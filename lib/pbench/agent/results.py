import datetime
import errno
import os
import tarfile
from configparser import ConfigParser
from logging import Logger
from pathlib import Path
from typing import IO, Iterator

import requests
from werkzeug.utils import secure_filename

from pbench.agent import PbenchAgentConfig
from pbench.common.exceptions import BadMDLogFormat
from pbench.common.utils import md5sum


class FileUploadError(Exception):
    """Raised when the uploading of file to server has failed"""

    pass


class MakeResultTb:
    """MakeResultTb - Creates the result tar file.

        TODO:  This is latent code -- it is currently unused and largely
               untested, intended to support the future implementation of
               a tool to replace pbench-make-result-tb.
    """

    def __init__(
        self,
        result_dir: str,
        target_dir: str,
        config: PbenchAgentConfig,
        logger: Logger,
    ):
        """__init__ - Initializes the required attributes

            Args:
                result_dir -- directory where tb file is collected.
                target_dir -- directory where tar file needs to be moved.
                config -- PbenchAgent config object
                logger -- logger objects helps logging important details
        """
        assert (
            config and logger
        ), f"config, '{config!r}', and/or logger, '{logger!r}', not provided"
        self.result_dir = self.check_result_target_dir(result_dir, "Result")
        self.target_dir = self.check_result_target_dir(target_dir, "Target")
        self.config = config
        self.logger = logger

    @staticmethod
    def check_result_target_dir(dir_path: str, name: str) -> Path:
        """check_result_target_dir - confirms the availability and
                integrity of the specified directory.
        """
        if not dir_path:
            raise FileNotFoundError(f"{name} directory not provided")
        else:
            try:
                path = Path(dir_path).resolve(strict=True)
            except Exception as exc:
                raise FileNotFoundError(
                    f"Invalid {name} directory provided: {dir_path}, ({exc})"
                )
            else:
                if not Path(dir_path).is_dir():
                    raise NotADirectoryError(
                        f"Invalid {name} directory provided: {dir_path}"
                    )
        return path

    def make_result_tb(self) -> str:
        """make_result_tb - make the result tarball.

            Returns
                -- tarball path
        """
        if os.path.exists(f"{self.result_dir}.copied"):
            raise Exception(f"Already copied {str(self.result_dir)}")

        pbench_run_name = self.result_dir.name
        if os.path.exists(f"{self.result_dir}/.running"):
            raise RuntimeError(
                f"The benchmark is still running in {pbench_run_name} - skipping; "
                f"if that is not true, rmdir {pbench_run_name}/.running, "
                "and try again",
            )

        mdlog_name = self.result_dir / "metadata.log"
        mdlog = ConfigParser()
        try:
            with mdlog_name.open("r") as fp:
                mdlog.read_file(fp)
        except Exception as exc:
            raise FileNotFoundError(
                f"The {pbench_run_name}/metadata.log file seems to be missing,"
                f" ({exc})"
            )

        md_config = mdlog["pbench"]
        res_name = md_config.get("name")
        if res_name != pbench_run_name:
            raise BadMDLogFormat(
                f"The run in directory {self.config.pbench_run / pbench_run_name}"
                f" has an unexpected metadata name, '{res_name}' - skipping"
            )

        result_size = sum(f.stat().st_size for f in self.result_dir.rglob("*"))
        self.logger.debug(
            "Preparing to tar up {} bytes of data from {}",
            result_size,
            self.result_dir,
        )
        mdlog.set("run", "raw_size", f"{result_size}")

        timestamp = datetime.datetime.isoformat(datetime.datetime.now())
        mdlog.set("pbench", "tar-ball-creation-timestamp", f"{timestamp}")

        with mdlog_name.open("w") as fp:
            mdlog.write(fp)

        tarball = self.target_dir / f"{pbench_run_name}.tar.xz"
        try:
            with tarfile.open(tarball, mode="x:xz") as tar:
                for f in self.result_dir.rglob("*"):
                    tar.add(os.path.realpath(f))
        except tarfile.TarError:
            self.logger.error(
                "Tar ball creation failed for {}, skipping", self.result_dir
            )
            try:
                tarball.unlink()
            except Exception as exc:
                if not isinstance(exc, OSError) or exc.errno != errno.ENOENT:
                    raise RuntimeError(
                        f"Error removing failed tarball, '{tarball}', {exc}"
                    )

        # The contract with the caller is to just return the full path to the
        # created tarball.
        return str(tarball)


class CopyResultTb:
    """CopyResultTb - Use the server's HTTP PUT method to upload a tarball
    """

    chunk_size = 4096

    def __init__(
        self, controller: str, tarball: str, config: PbenchAgentConfig, logger: Logger
    ):
        self.tarball = Path(tarball)
        if not self.tarball.exists():
            raise FileNotFoundError(f"Tarball '{self.tarball}' does not exist")
        self.logger = logger
        server_rest_url = config.get("results", "server_rest_url")
        self.upload_url = f"{server_rest_url}/upload/ctrl/{controller}"

    def read_in_chunks(self, file_object: IO) -> Iterator[bytes]:
        data = file_object.read(self.chunk_size)
        while data:
            yield data
            data = file_object.read(self.chunk_size)

    def copy_result_tb(self, token: str) -> None:
        """copy_result_tb - copies tb from agent to configured server upload URL

            Args
                token -- a token which establishes that the caller is
                    authorized to make the PUT request on behalf of a
                    specific user.
        """
        content_length, content_md5 = md5sum(self.tarball)
        headers = {
            "filename": secure_filename(str(self.tarball)),
            "Content-MD5": content_md5,
            "Content-Length": str(content_length),
            "Authorization": f"Bearer {token}",
        }
        with self.tarball.open("rb") as f:
            try:
                response = requests.put(
                    self.upload_url, data=self.read_in_chunks(f), headers=headers
                )
                response.raise_for_status()
                self.logger.info("File uploaded successfully")
            except requests.exceptions.ConnectionError:
                raise RuntimeError(f"Cannot connect to '{self.upload_url}'")
            except Exception as exc:
                raise FileUploadError(
                    "There was something wrong with file upload request:  "
                    f"file: '{self.tarball}', URL: '{self.upload_url}', ({exc})"
                )
        assert (
            response.ok
        ), f"Logic bomb!  Unexpected error response, '{response.reason}' ({response.status_code})"
