import collections
import datetime
import os
import subprocess
import urllib.parse
from distutils.spawn import find_executable
from logging import Logger
from pathlib import Path

import requests

from pbench.agent import PbenchAgentConfig
from pbench.common import MetadataLog
from pbench.common.exceptions import BadMDLogFormat
from pbench.common.utils import md5sum, validate_hostname


TarballRecord = collections.namedtuple("TarballRecord", ["name", "length", "md5"])


class MakeResultTb:
    """Interfaces for managing the creation a result tar ball.

    """

    class AlreadyCopied(RuntimeError):
        """Specific run time error raised when a result directory has a .copied
        marker present.
        """

        pass

    class BenchmarkRunning(RuntimeError):
        """Specific run time error raised when a result directory has a .running
        marker present.
        """

        pass

    def __init__(
        self,
        result_dir: str,
        target_dir: str,
        controller: str,
        config: PbenchAgentConfig,
        logger: Logger,
    ):
        """Initializes the required attributes for making a tar ball

        Args:
            result_dir -- results directory from which a tar ball will be
                          constructed
            target_dir -- target directory where the tar ball should be placed
            controller -- the name of the controller to be associated with the
                          tar ball
            config -- PbenchAgent config object
            logger -- logger object to use when emitting log entries during
                      operation

        Raises:
            AlreadyCopied       if we find a "*.copied" marker for the result
                                directory.
            BenchmarkRunning    if we find a "*/.running" marker in the result
                                directory.
            FileNotFoundError   if either the result or target directories do
                                not exist
            NotADirectoryError  if either the result or target directories are
                                not actual directories
            RuntimeError        if it cannot find the 'tar' command on the PATH
            ValueError          if the given controller is not a valid host
                                name
        """
        assert (
            config and logger
        ), f"config, '{config!r}', and/or logger, '{logger!r}', not provided"
        self.tar_path = find_executable("tar")
        if self.tar_path is None:
            raise RuntimeError(f"External 'tar' executable not found")
        self.xz_path = find_executable("xz")
        if self.xz_path is None:
            raise RuntimeError(f"External 'xz' executable not found")
        self.result_dir = self._check_result_target_dir(result_dir, "Result")
        self.target_dir = self._check_result_target_dir(target_dir, "Target")
        self.config = config
        self.logger = logger
        if validate_hostname(controller) != 0:
            raise ValueError(f"Controller {controller!r} is not a valid host name")
        self.controller = controller
        if (self.result_dir.parent / f"{self.result_dir.name}.copied").exists():
            raise self.AlreadyCopied(f"Already copied {self.result_dir.name}")
        if (self.result_dir / ".running").exists():
            raise self.BenchmarkRunning(
                f"The benchmark is still running in {self.result_dir.name} - skipping; "
                f"if that is not true, rmdir {self.result_dir.name}/.running, "
                "and try again",
            )

    @staticmethod
    def _check_result_target_dir(dir_path: str, name: str) -> Path:
        """Confirms the availability and integrity of the specified directory.
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

    def make_result_tb(self, single_threaded: bool = False) -> TarballRecord:
        """Make the result tar ball from result directory.

        The metadata.log file in the result directory is double checked to be
        sure it is valid, and then the "run.raw_size" and the
        "pbench.tar-ball-creation-timestamp" fields are added.

        The tar ball is created, verified, and the MD5 sum value is generated.

        Returns a tuple of the Path object of the create tar ball, its length,
        and its MD5 checksum value.

        Raises
          - FileNotFoundError  if the result directory does not have a
                               metadata.log file
          - BadMDLogFormat     if the metadata.log file has a pbench.name field
                               value which does not match the result directory
                               name.
          - RuntimeError       if any problems are encountered while creating
                               or verifying the created tar ball
        """
        pbench_run_name = self.result_dir.name
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

        mdlog.set("pbench", "hostname_f", os.environ.get("_pbench_full_hostname", ""))
        mdlog.set("pbench", "hostname_s", os.environ.get("_pbench_hostname", ""))
        mdlog.set("pbench", "hostname_ip", os.environ.get("_pbench_hostname_ip", ""))

        md_run = mdlog["run"]
        md_controller = md_run.get("controller", "")
        if md_controller != self.controller:
            # The controller name in the metadata.log file does not match the
            # controller directory being used in the target directory.  So
            # save the current controller as "controller_orig", and save the
            # controller directory as the new controller name.
            if md_controller:
                mdlog.set("run", "controller_org", md_controller)
            mdlog.set("run", "controller", self.controller)

        result_size = sum(f.stat().st_size for f in self.result_dir.rglob("*"))
        self.logger.debug(
            "Preparing to tar up %d bytes of data from %s",
            result_size,
            self.result_dir,
        )
        mdlog.set("run", "raw_size", f"{result_size}")

        timestamp = datetime.datetime.isoformat(datetime.datetime.now())
        mdlog.set("pbench", "tar-ball-creation-timestamp", f"{timestamp}")

        with mdlog_name.open("w") as fp:
            mdlog.write(fp)

        # FIXME: /bin/cp pbench.log ${pbench_run_name}/

        tarball = self.target_dir / f"{pbench_run_name}.tar.xz"
        e_file = self.target_dir / f"{pbench_run_name}.tar.err"
        args = [self.tar_path, "--create", "--force-local"]
        if single_threaded:
            args.append("--xz")
        args.append(pbench_run_name)
        try:
            # Invoke tar directly for efficiency.
            if single_threaded:
                with tarball.open("w") as ofp, e_file.open("w") as efp:
                    tar_proc = subprocess.Popen(
                        args,
                        cwd=str(self.result_dir.parent),
                        stdin=None,
                        stdout=ofp,
                        stderr=efp,
                    )
                    tar_proc.wait()
                xz_proc = None
            else:
                with tarball.open("w") as ofp, e_file.open("w") as efp:
                    xz_proc = subprocess.Popen(
                        [self.xz_path, "-T0"],
                        cwd=str(self.target_dir),
                        stdin=subprocess.PIPE,
                        stdout=ofp,
                        stderr=efp,
                    )
                    tar_proc = subprocess.Popen(
                        args,
                        cwd=str(self.result_dir.parent),
                        stdin=None,
                        stdout=xz_proc.stdin,
                        stderr=efp,
                    )
                    tar_proc.wait()
                    # Now that the `tar` command has exited, we close the
                    # `stdin` of the `xz` command to shut it down.
                    xz_proc.stdin.close()
                    xz_proc.wait()
        except Exception as exc:
            msg = f"Tar ball creation failed for {self.result_dir}, skipping {exc}"
            try:
                tarball.unlink()
            except FileNotFoundError:
                pass
            except Exception as unlink_exc:
                msg = f"{msg}; also encountered an error while removing failed tar ball, {tarball}: '{unlink_exc}'"
            raise RuntimeError(msg)
        else:
            if tar_proc.returncode == 0:
                if xz_proc is not None and xz_proc.returncode != 0:
                    msg = f"Failed to create tar ball; 'xz' return code: {xz_proc.returncode:d}"
                    try:
                        tarball.unlink()
                    except FileNotFoundError:
                        pass
                    except Exception as unlink_exc:
                        msg = f"{msg}; also encountered an error while removing failed tar ball, {tarball}: '{unlink_exc}'"
                    raise RuntimeError(msg)
                else:
                    try:
                        e_file.unlink()
                    except FileNotFoundError:
                        pass
                    except Exception as unlink_exc:
                        self.logger.warning(
                            "Failed to remove 'tar' stderr file, %s: '%s'",
                            e_file,
                            unlink_exc,
                        )
            else:
                # We explicitly ignore the return code from the optional 'xz' process.
                msg = f"Failed to create tar ball; 'tar' return code: {tar_proc.returncode:d}"
                try:
                    tarball.unlink()
                except FileNotFoundError:
                    pass
                except Exception as unlink_exc:
                    msg = f"{msg}; also encountered an error while removing failed tar ball, {tarball}: '{unlink_exc}'"
                raise RuntimeError(msg)
        try:
            (tar_len, tar_md5) = md5sum(tarball)
        except Exception:
            msg = f"Failed to verify and generate MD5 for created tar ball, '{tarball}'"
            try:
                tarball.unlink()
            except FileNotFoundError:
                pass
            except Exception as unlink_exc:
                msg = f"{msg}; also encountered an error while removing failed tar ball, {tarball}: '{unlink_exc}'"
            raise RuntimeError(msg)

        # The contract with the caller is to just return the full path to the
        # created tar ball.
        return TarballRecord(tarball, tar_len, tar_md5)


class CopyResultTb:
    """Interfaces for copying result tar balls remotely using the server's HTTP
    PUT method for uploads.
    """

    class FileUploadError(Exception):
        """Raised when the uploading of file to server has failed"""

        pass

    def __init__(
        self,
        controller: str,
        tarball: str,
        tarball_len: int,
        tarball_md5: str,
        config: PbenchAgentConfig,
        logger: Logger,
    ):
        """Contructor for object representing tar ball to be copied remotely.

        Raises
            ValueError          if the given controller is not a valid hostname
            FileNotFoundError   if the given tar ball does not exist
        """
        self.controller = controller
        self.tarball = Path(tarball)
        if not self.tarball.exists():
            raise FileNotFoundError(f"Tar ball '{self.tarball}' does not exist")
        self.tarball_len = tarball_len
        self.tarball_md5 = tarball_md5
        server_rest_url = config.get("results", "server_rest_url")
        tbname = urllib.parse.quote(self.tarball.name)
        self.upload_url = f"{server_rest_url}/upload/{tbname}"
        self.logger = logger

    def copy_result_tb(self, token: str) -> None:
        """Copies the tar ball from the agent to the configured server using upload
        API.

        Args
            token -- a token which establishes that the caller is
                authorized to make the PUT request on behalf of a
                specific user.

        Raises
            RuntimeError     if a connection fails to be make to the server
            FileUploadError  if the tar balls to upload properly

        """
        headers = {
            "Content-MD5": self.tarball_md5,
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
                assert request.headers["Content-Length"] == str(self.tarball_len), (
                    "Upload request `Content-Length` header contains {} -- "
                    "expected {}".format(
                        request.headers["Content-Length"], self.tarball_len
                    )
                )

                response = requests.Session().send(request)
                response.raise_for_status()
                self.logger.info("File uploaded successfully")
            except requests.exceptions.ConnectionError:
                raise RuntimeError(f"Cannot connect to '{self.upload_url}'")
            except Exception as exc:
                raise self.FileUploadError(
                    "There was something wrong with file upload request: "
                    f"file: '{self.tarball}', URL: '{self.upload_url}';"
                    f" error: '{exc}'"
                )
        assert (
            response.ok
        ), f"Logic bomb!  Unexpected error response, '{response.reason}' ({response.status_code})"
