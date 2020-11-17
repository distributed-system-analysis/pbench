import os
import humanize
import tempfile
import hashlib
from pathlib import Path
from flask_restful import Resource, abort
from flask import request, jsonify
from werkzeug.utils import secure_filename
from pbench.server.utils import filesize_bytes

ALLOWED_EXTENSIONS = {"xz"}


class HostInfo(Resource):
    def __init__(self, config, logger):
        self.logger = logger
        self.user = config.get_conf(__name__, "pbench-server", "user", self.logger)
        self.host = config.get_conf(__name__, "pbench-server", "host", self.logger)
        self.prdp = config.get_conf(
            __name__, "pbench-server", "pbench-receive-dir-prefix", self.logger
        )

    def get(self):
        try:
            response = jsonify(
                dict(message=f"{self.user}@{self.host}" f":{self.prdp}-002")
            )
        except Exception:
            self.logger.exception(
                "There was something wrong constructing the host info"
            )
            abort(500, message="INTERNAL ERROR")
        response.status_code = 200
        return response


class Upload(Resource):
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.max_content_length = filesize_bytes(
            self.config.get_conf(
                __name__, "pbench-server", "rest_max_content_length", self.logger
            )
        )

    def put(self, controller):
        if not request.headers.get("filename"):
            self.logger.debug(
                "Tarfile upload: Post operation failed due to missing filename header"
            )
            abort(
                400,
                message="Missing filename header, POST operation requires a filename header to name the uploaded file",
            )
        filename = secure_filename(request.headers.get("filename"))

        if not request.headers.get("Content-MD5"):
            self.logger.debug(
                f"Tarfile upload: Post operation failed due to missing md5sum header for file {filename}"
            )
            abort(
                400,
                message="Missing md5sum header, POST operation requires md5sum of an uploaded file in header",
            )
        md5sum = request.headers.get("Content-MD5")

        self.logger.debug("Receiving file: {}", filename)
        if not self.allowed_file(filename):
            self.logger.debug(
                f"Tarfile upload: Bad file extension received for file {filename}"
            )
            abort(400, message="File extension not supported. Only .xz")

        try:
            content_length = int(request.headers.get("Content-Length"))
        except ValueError:
            self.logger.debug(
                f"Tarfile upload: Invalid content-length header, not an integer for file {filename}"
            )
            abort(400, message="Invalid content-length header, not an integer")
        except Exception:
            self.logger.debug(
                f"Tarfile upload: No Content-Length header value found for file {filename}"
            )
            abort(400, message="Missing required content-length header")
        else:
            if content_length > self.max_content_length:
                self.logger.debug(
                    f"Tarfile upload: Content-Length exceeded maximum upload size allowed. File: {filename}"
                )
                abort(
                    400,
                    message=f"Payload body too large, {content_length:d} bytes, maximum size should be less than "
                    f"or equal to {humanize.naturalsize(self.max_content_length)}",
                )
            elif content_length == 0:
                self.logger.debug(
                    f"Tarfile upload: Content-Length header value is 0 for file {filename}"
                )
                abort(
                    400,
                    message="Upload failed, Content-Length received in header is 0",
                )

        path = self.upload_directory / controller
        path.mkdir(exist_ok=True)
        tar_full_path = Path(path, filename)
        md5_full_path = Path(path, f"{filename}.md5")
        bytes_received = 0

        with tempfile.NamedTemporaryFile(mode="wb", dir=path) as ofp:
            chunk_size = 4096
            self.logger.debug("Writing chunks")
            hash_md5 = hashlib.md5()

            try:
                while True:
                    chunk = request.stream.read(chunk_size)
                    bytes_received += len(chunk)
                    if len(chunk) == 0 or bytes_received > content_length:
                        break

                    ofp.write(chunk)
                    hash_md5.update(chunk)
            except Exception:
                self.logger.exception(
                    "Tarfile upload: There was something wrong uploading {}", filename
                )
                abort(500, message=f"There was something wrong uploading {filename}")

            if bytes_received != content_length:
                self.logger.debug(
                    f"Tarfile upload: Bytes received does not match with content length header value for file {filename}"
                )
                message = (
                    f"Bytes received ({bytes_received}) does not match with content length header"
                    f" ({content_length}), upload failed"
                )
                abort(400, message=message)

            elif hash_md5.hexdigest() != md5sum:
                self.logger.debug(
                    f"Tarfile upload: md5sum check failed for file {filename}"
                )
                message = f"md5sum check failed for {filename}, upload failed"
                abort(400, message=message)

            # First write the .md5
            try:
                with md5_full_path.open("w") as md5fp:
                    md5fp.write(f"{md5sum} {filename}\n")
            except Exception:
                try:
                    os.remove(md5_full_path)
                except FileNotFoundError:
                    pass
                except Exception as exc:
                    self.logger.warning(
                        "Failed to remove .md5 %s when trying to clean up: %s",
                        md5_full_path,
                        exc,
                    )
                self.logger.exception("Failed to write .md5 file, '%s'", md5_full_path)
                raise

            # Then create the final filename link to the temporary file.
            try:
                os.link(ofp.name, tar_full_path)
            except Exception:
                try:
                    os.remove(md5_full_path)
                except Exception as exc:
                    self.logger.warning(
                        "Failed to remove .md5 %s when trying to clean up: %s",
                        md5_full_path,
                        exc,
                    )
                self.logger.exception(
                    "Failed to rename tar ball '%s' to '%s'", ofp.name, md5_full_path,
                )
                raise

        response = jsonify(dict(message="File successfully uploaded"))
        response.status_code = 201
        return response

    @staticmethod
    def allowed_file(filename):
        """Check if the file has the correct extension."""
        try:
            fn = filename.rsplit(".", 1)[1].lower()
        except IndexError:
            return False
        allowed = "." in filename and fn in ALLOWED_EXTENSIONS
        return allowed

    @property
    def upload_directory(self):
        prdp = self.config.get_conf(
            __name__, "pbench-server", "pbench-receive-dir-prefix", self.logger
        )
        try:
            return Path(f"{prdp}-002").resolve(strict=True)
        except FileNotFoundError:
            self.logger.exception(
                "pbench-receive-dir-prefix does not exist on the host"
            )
            raise FileNotFoundError(
                "pbench-receive-dir-prefix does not exist on the host"
            )
        except Exception:
            self.logger.exception(
                "Exception occurred during setting up the upload directory on the host"
            )
            raise Exception(
                "Some Exception occurred during setting up the upload directory on the host"
            )
