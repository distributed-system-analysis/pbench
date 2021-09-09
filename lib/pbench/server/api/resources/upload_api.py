import datetime
import errno
import hashlib
import os
import tempfile
from http import HTTPStatus
from pathlib import Path

import humanize
from flask import jsonify, request
from flask_restful import Resource, abort

from pbench.common.utils import validate_hostname
from pbench.server.api.auth import Auth
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetDuplicate,
    States,
    Metadata,
)
from pbench.server.utils import filesize_bytes


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
        except Exception as exc:
            self.logger.error(
                "There was something wrong constructing the host info: '{}'", exc
            )
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
        response.status_code = HTTPStatus.OK
        return response


class Upload(Resource):
    ALLOWED_EXTENSION = ".tar.xz"
    CHUNK_SIZE = 65536

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.max_content_length = filesize_bytes(
            self.config.get_conf(
                __name__, "pbench-server", "rest_max_content_length", self.logger
            )
        )

    @Auth.token_auth.login_required()
    def put(self, filename: str):
        try:
            username = Auth.token_auth.current_user().username
        except Exception as exc:
            self.logger.error("Error verifying the username: '{}'", exc)
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        if os.path.basename(filename) != filename:
            msg = "File must not contain a path"
            self.logger.warning(
                "{} for user = {}, file = {!a}", msg, username, filename,
            )
            abort(HTTPStatus.BAD_REQUEST, message=msg)

        if not self.supported_file_extension(filename):
            msg = f"File extension not supported, must be {self.ALLOWED_EXTENSION}"
            self.logger.warning(
                "{} for user = {}, file = {!a}", msg, username, filename,
            )
            abort(HTTPStatus.BAD_REQUEST, message=msg)

        controller = request.headers.get("controller")
        if not controller:
            msg = "Missing required controller header"
            self.logger.warning(
                "{} for user = {}, file = {!a}", msg, username, filename
            )
            abort(HTTPStatus.BAD_REQUEST, message=msg)
        if validate_hostname(controller) != 0:
            msg = "Invalid controller header"
            self.logger.warning(
                "{} for user = {}, ctrl = {!a}, file = {!a}",
                msg,
                username,
                controller,
                filename,
            )
            abort(HTTPStatus.BAD_REQUEST, message=msg)

        md5sum = request.headers.get("Content-MD5")
        if not md5sum:
            msg = "Missing required Content-MD5 header"
            self.logger.warning(
                "{} for user = {}, ctrl = {!a}, file = {!a}",
                msg,
                username,
                controller,
                filename,
            )
            abort(HTTPStatus.BAD_REQUEST, message=msg)

        status = HTTPStatus.OK
        try:
            content_length = int(request.headers["Content-Length"])
        except KeyError:
            msg = "Missing required Content-Length header"
            status = HTTPStatus.LENGTH_REQUIRED
        except ValueError:
            msg = f"Invalid Content-Length header, not an integer ({content_length})"
            status = HTTPStatus.BAD_REQUEST
        else:
            if not (0 < content_length <= self.max_content_length):
                msg = "Content-Length ({}) must be greater than 0 and no greater than {}".format(
                    content_length, humanize.naturalsize(self.max_content_length)
                )
                status = (
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE
                    if 0 < content_length
                    else HTTPStatus.BAD_REQUEST
                )
        if status != HTTPStatus.OK:
            self.logger.warning(
                "{} for user = {}, ctrl = {!a}, file = {!a}",
                msg,
                username,
                controller,
                filename,
            )
            abort(status, message=msg)

        path = self.upload_directory / controller
        path.mkdir(exist_ok=True)
        tar_full_path = Path(path, filename)
        md5_full_path = Path(path, f"{filename}.md5")
        bytes_received = 0

        # Create a tracking dataset object; it'll begin in UPLOADING state
        try:
            dataset = Dataset(
                owner=username, controller=controller, path=tar_full_path, md5=md5sum
            )
            dataset.add()
        except DatasetDuplicate:
            self.logger.info(
                "Dataset already exists, user = {}, ctrl = {!a}, file = {!a}",
                username,
                controller,
                filename,
            )
            response = jsonify(dict(message="Dataset already exists"))
            response.status_code = HTTPStatus.OK
            return response
        except Exception as exc:
            self.logger.error(
                "unable to create dataset, '{}', for user = {}, ctrl = {!a}, file = {!a}",
                exc,
                username,
                controller,
                filename,
            )
            abort(
                HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR",
            )

        if tar_full_path.is_file() or md5_full_path.is_file():
            self.logger.error(
                "Dataset, or corresponding md5 file, already present; tar {} ({}), md5 {} ({})",
                tar_full_path,
                "present" if tar_full_path.is_file() else "missing",
                md5_full_path,
                "present" if md5_full_path.is_file() else "missing",
            )
            abort(
                HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR",
            )

        self.logger.info(
            "Uploading file {!a} (user = {}, ctrl = {!a}) to {}",
            filename,
            username,
            controller,
            dataset,
        )

        with tempfile.NamedTemporaryFile(mode="wb", dir=path) as ofp:
            hash_md5 = hashlib.md5()

            try:
                while True:
                    chunk = request.stream.read(self.CHUNK_SIZE)
                    bytes_received += len(chunk)
                    if len(chunk) == 0 or bytes_received > content_length:
                        break

                    ofp.write(chunk)
                    hash_md5.update(chunk)
            except OSError as exc:
                if exc.errno == errno.ENOSPC:
                    self.logger.error(
                        "Not enough space on volume, {}, for upload:"
                        " user = {}, ctrl = {!a}, file = {!a}",
                        path,
                        username,
                        controller,
                        filename,
                    )
                    abort(HTTPStatus.INSUFFICIENT_STORAGE)
                else:
                    msg = "Unexpected error encountered during file upload"
                    self.logger.error(
                        "{}, {}, for user = {}, ctrl = {!a}, file = {!a}",
                        msg,
                        exc,
                        username,
                        controller,
                        filename,
                    )
                    abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
            except Exception as exc:
                msg = "Unexpected error encountered during file upload"
                self.logger.error(
                    "{}, {}, for user = {}, ctrl = {!a}, file = {!a}",
                    msg,
                    exc,
                    username,
                    controller,
                    filename,
                )
                abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

            if bytes_received != content_length:
                msg = (
                    "Bytes received do not match Content-Length header"
                    f" (expected {content_length}; received {bytes_received})"
                )
                self.logger.warning(
                    "{} for user = {}, ctrl = {!a}, file = {!a}",
                    msg,
                    username,
                    controller,
                    filename,
                )
                abort(HTTPStatus.BAD_REQUEST, message=msg)
            elif hash_md5.hexdigest() != md5sum:
                msg = (
                    "MD5 checksum does not match Content-MD5 header"
                    f" ({hash_md5.hexdigest()} != {md5sum})"
                )
                self.logger.warning(
                    "{} for user = {}, ctrl = {!a}, file = {!a}",
                    msg,
                    username,
                    controller,
                    filename,
                )
                abort(HTTPStatus.BAD_REQUEST, message=msg)

            # First write the .md5
            try:
                md5_full_path.write_text(f"{md5sum} {filename}\n")
            except Exception as exc:
                try:
                    md5_full_path.unlink(missing_ok=True)
                except Exception as md5_exc:
                    self.logger.error(
                        "Failed to remove .md5 {} when trying to clean up: '{}'",
                        md5_full_path,
                        md5_exc,
                    )
                self.logger.error(
                    "Failed to write .md5 file, '{}': '{}'", md5_full_path, exc
                )
                abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

            # Then create the final filename link to the temporary file.
            try:
                os.link(ofp.name, tar_full_path)
            except Exception as exc:
                try:
                    md5_full_path.unlink()
                except Exception as md5_exc:
                    self.logger.error(
                        "Failed to remove .md5 {} when trying to clean up: {}",
                        md5_full_path,
                        md5_exc,
                    )
                self.logger.error(
                    "Failed to rename tar ball '{}' to '{}': '{}'",
                    ofp.name,
                    md5_full_path,
                    exc,
                )
                abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")

        try:
            dataset.advance(States.UPLOADED)

            # NOTE: Metadata.SAVED and Metadata.SEEN are on the `dashboard` key
            # while Metadata.DELETION is on `server`. We could still combine
            # these two as `Metadata.create(dataset=dataset, key="dashboard",
            # value={"saved": False, "seen": False})` and save a few DB
            # operations. However, using separate `setvalue` operations has the
            # advantage of not requiring any assumptions about the organization
            # of the attributes, which is more maintainable.
            Metadata.setvalue(dataset=dataset, key=Metadata.SAVED, value=False)
            Metadata.setvalue(dataset=dataset, key=Metadata.SEEN, value=False)

            # TODO: Implement per-user override of default (requires PR #2049)
            try:
                retention_days = int(
                    self.config.get_conf(
                        __name__, "pbench-server", "default-dataset-retention", 90
                    )
                )
            except Exception as e:
                self.logger.error("Unable to get integer retention days: {}", str(e))
                raise
            retention = datetime.timedelta(days=retention_days)
            deletion = datetime.datetime.now() + retention
            Metadata.setvalue(
                dataset=dataset, key=Metadata.DELETION, value=f"{deletion:%Y-%m-%d}"
            )
        except Exception as exc:
            self.logger.error("Unable to finalize {}, '{}'", dataset, exc)
            abort(HTTPStatus.INTERNAL_SERVER_ERROR, message="INTERNAL ERROR")
        response = jsonify(dict(message="File successfully uploaded"))
        response.status_code = HTTPStatus.CREATED
        return response

    @staticmethod
    def supported_file_extension(filename: str) -> bool:
        """Check if the given file name ends with the allowed extension.

        Return True if the allowed extension is found, False otherwise.
        """
        return filename.endswith(Upload.ALLOWED_EXTENSION)

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
