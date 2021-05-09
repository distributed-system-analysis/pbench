import datetime
import errno
import os
import tarfile
import urllib.parse
from logging import Logger
from pathlib import Path

import requests

from pbench.agent import PbenchAgentConfig
from pbench.common import MetadataLog
from pbench.common.exceptions import BadMDLogFormat
from pbench.common.utils import md5sum, validate_hostname


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
        mdlog = MetadataLog()
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

    def __init__(
        self, controller: str, tarball: str, config: PbenchAgentConfig, logger: Logger
    ):
        """CopyResultTb contructor - raises FileNotFoundError if the given
        tar ball does not exist, and a ValueError if the given controller is
        not a valid hostname.
        """
        if validate_hostname(controller) != 0:
            raise ValueError(f"Controller {controller!r} is not a valid host name")
        self.controller = controller
        self.tarball = Path(tarball)
        if not self.tarball.exists():
            raise FileNotFoundError(f"Tarball '{self.tarball}' does not exist")
        server_rest_url = config.get("results", "server_rest_url")
        tbname = urllib.parse.quote(self.tarball.name)
        self.upload_url = f"{server_rest_url}/upload/{tbname}"
        self.logger = logger

    def copy_result_tb(self, token: str) -> None:
        """copy_result_tb - copies tb from agent to configured server upload URL

            Args
                token -- a token which establishes that the caller is
                    authorized to make the PUT request on behalf of a
                    specific user.
        """
        content_length, content_md5 = md5sum(str(self.tarball))
        headers = {
            "Content-MD5": content_md5,
            "Authorization": f"Bearer {token}",
            "controller": self.controller,
        }
        with self.tarball.open("rb") as f:
            try:
                request = requests.Request(
                    "PUT", self.upload_url, data=f, headers=headers
                ).prepare()

                # Per RFC 2616, a request must not contain both
                # Content-Length and Transfer-Encoding headers; however,
                # the server would like to receive the Content-Length
                # header, but the requests package may opt to generate
                # the Transfer-Encoding header instead...so, check that
                # we got what we want before we send the request.  Also,
                # confirm that the contents of the Content-Length header
                # is what we expect.
                assert (
                    "Transfer-Encoding" not in request.headers
                ), "Upload request unexpectedly contains a `Transfer-Encoding` header"
                assert (
                    "Content-Length" in request.headers
                ), "Upload request unexpectedly missing a `Content-Length` header"
                assert request.headers["Content-Length"] == str(content_length), (
                    "Upload request `Content-Length` header contains {} -- "
                    "expected {}".format(
                        request.headers["Content-Length"], content_length
                    )
                )

                response = requests.Session().send(request)
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
