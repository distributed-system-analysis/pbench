import requests

from logging import Logger
from pathlib import Path


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
        upload_url: str,
        logger: Logger,
    ):
        """Constructor for object representing tar ball to be copied remotely.

        Raises
            FileNotFoundError   if the given tar ball does not exist
        """
        self.controller = controller
        self.tarball = Path(tarball)
        if not self.tarball.exists():
            raise FileNotFoundError(f"Tar ball '{self.tarball}' does not exist")
        self.tarball_len = tarball_len
        self.tarball_md5 = tarball_md5
        self.upload_url = upload_url
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
                self.logger.info(
                    "File uploaded successfully: {} on target address, {}",
                    self.tarball,
                    self.upload_url,
                )
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
