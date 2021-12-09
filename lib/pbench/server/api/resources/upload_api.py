from collections import deque
import datetime
import errno
import hashlib
from logging import Logger
import os
from http import HTTPStatus
from typing import Callable, Deque

import humanize
from flask import jsonify, request
from flask_restful import Resource, abort

from pbench.common.utils import validate_hostname
from pbench.server import PbenchServerConfig
from pbench.server.filetree import DatasetNotFound, FileTree, Tarball
from pbench.server.api.auth import Auth
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetDuplicate,
    States,
    Metadata,
)
from pbench.server.utils import filesize_bytes


class CleanupTime(Exception):
    """
    Used to support handling errors during PUT without constantly testing the
    current status and additional indentation. This will be raised to an outer
    try block when an error occurs.
    """

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


class CleanupAction:
    """
    Define a single cleanup action necessary to reverse persistent steps in the
    upload procedure, based on the Step ENUM associated with the action.
    """

    def __init__(self, logger: Logger, action: Callable, name: str = None):
        """
        Define a cleanup action

        Args:
            logger: The active Pbench Logger object
            action: a Callable to perform cleanup
            name: informative string
        """
        self.action = action
        self.name = name
        self.logger = logger

    def cleanup(self):
        """
        Perform a cleanup action depending on the associated Step value.

        This handles errors and reports them, but doesn't propagate failure to
        ensure that cleanup continues as best we can.
        """
        try:
            self.action()
        except Exception as e:
            self.logger.error("Unable to revert {}: {}", self.name, e)


class Cleanup:
    """
    Maintain and process a deque of cleanup actions accumulated during the
    upload procedure. Cleanup actions will be processed in reverse of the
    order they were registered.
    """

    def __init__(self, logger: Logger):
        """
        Define a deque on which cleanup actions will be recorded, and attach
        a Pbench Logger object to report errors.

        Args:
            logger: Pbench Logger
        """
        self.logger = logger
        self.actions: Deque[CleanupAction] = deque()

    def add(self, action: Callable, name: str = None) -> None:
        """
        Add a new cleanup action to the front of the deque

        Args:
            step: Step ENUM value describing the cleanup action
            parameter: A parameter for the cleanup action
        """
        self.actions.appendleft(CleanupAction(self.logger, action, name))

    def cleanup(self):
        """
        Perform queued cleanup actions in order from most recent to oldest.
        """
        for action in self.actions:
            action.cleanup()


class Upload(Resource):
    """
    Upload a dataset from an agent. This API accepts a tarball, controller
    name, and MD5 value from a client. After validation, it creates a new
    Dataset DB row describing the dataset, along with some metadata, and it
    creates a pair of files (tarball and MD5 file) within the designated
    controller directory under the configured ARCHIVE file tree.
    """

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
        self.temporary = config.ARCHIVE / FileTree.TEMPORARY
        self.temporary.mkdir(mode=0o755, parents=True, exist_ok=True)
        self.logger.info("Configured PUT temporary directory as {}", self.temporary)

    @Auth.token_auth.login_required()
    def put(self, filename: str):

        # Used to record what steps have been completed during the upload, and
        # need to be undone on failure
        recovery = Cleanup(self.logger)

        try:
            try:
                username = Auth.token_auth.current_user().username
            except Exception:
                username = None
                raise CleanupTime(
                    HTTPStatus.INTERNAL_SERVER_ERROR, "Error verifying username"
                )

            controller = request.headers.get("controller")
            if not controller:
                raise CleanupTime(
                    HTTPStatus.BAD_REQUEST, "Missing required 'controller' header"
                )

            if validate_hostname(controller) != 0:
                raise CleanupTime(HTTPStatus.BAD_REQUEST, "Invalid 'controller' header")

            self.logger.info("Uploading {} on controller {}", filename, controller)

            if os.path.basename(filename) != filename:
                raise CleanupTime(
                    HTTPStatus.BAD_REQUEST, "Filename must not contain a path"
                )

            if not self.supported_file_extension(filename):
                raise CleanupTime(
                    HTTPStatus.BAD_REQUEST,
                    f"File extension not supported, must be {self.ALLOWED_EXTENSION}",
                )

            md5sum = request.headers.get("Content-MD5")
            if not md5sum:
                raise CleanupTime(
                    HTTPStatus.BAD_REQUEST, "Missing required 'Content-MD5' header"
                )

            try:
                length_string = request.headers["Content-Length"]
                content_length = int(length_string)
            except KeyError:
                # NOTE: Werkzeug is "smart" about header access, and knows that
                # Content-Length is an integer. Therefore, a non-integer value
                # will raise KeyError. It's virtually impossible to report the
                # actual incorrect value as we'd just get a KeyError again.
                raise CleanupTime(
                    HTTPStatus.LENGTH_REQUIRED,
                    "Missing or invalid 'Content-Length' header",
                )
            except ValueError:
                # NOTE: Because of the way Werkzeug works, this should not be
                # possible: if Content-Length isn't an integer, we'll see the
                # KeyError. This however serves as a clarifying backup case.
                raise CleanupTime(
                    HTTPStatus.BAD_REQUEST,
                    f"Invalid 'Content-Length' header, not an integer ({length_string})",
                )

            if content_length <= 0:
                raise CleanupTime(
                    HTTPStatus.BAD_REQUEST,
                    f"'Content-Length' {content_length} must be greater than 0",
                )
            elif content_length > self.max_content_length:
                raise CleanupTime(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    f"'Content-Length' {content_length} must be no greater than than {humanize.naturalsize(self.max_content_length)}",
                )

            tar_full_path = self.temporary / filename
            md5_full_path = self.temporary / f"{filename}.md5"
            bytes_received = 0

            self.logger.info(
                "PUT uploading {}:{} for user {} to {}",
                controller,
                filename,
                username,
                tar_full_path,
            )

            # Create a tracking dataset object; it'll begin in UPLOADING state
            try:
                dataset = Dataset(
                    owner=username,
                    controller=controller,
                    path=tar_full_path,
                    md5=md5sum,
                )
                dataset.add()
            except DatasetDuplicate:
                dataset_name = Tarball.stem(tar_full_path)
                self.logger.info(
                    "Dataset already exists, user = {}, ctrl = {!a}, file = {!a}",
                    username,
                    controller,
                    dataset_name,
                )
                try:
                    duplicate = Dataset.query(controller=controller, name=dataset_name)
                except DatasetNotFound:
                    self.logger.error(
                        "Duplicate dataset {}:{}:{} not found",
                        username,
                        controller,
                        dataset_name,
                    )
                    raise CleanupTime(
                        HTTPStatus.INTERNAL_SERVER_ERROR, "INTERNAL ERROR"
                    )
                else:
                    if duplicate.md5 == md5sum:
                        response = jsonify(dict(message="Dataset already exists"))
                        response.status_code = HTTPStatus.OK
                        return response
                    else:
                        raise CleanupTime(
                            HTTPStatus.CONFLICT,
                            f"Duplicate dataset has different MD5 ({duplicate.md5} != {md5sum})",
                        )
            except CleanupTime:
                pass
            except Exception:
                raise CleanupTime(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    message="Unable to create dataset",
                )

            recovery.add(dataset.delete, "delete dataset")

            self.logger.info(
                "Uploading file {!a} (user = {}, ctrl = {!a}) to {}",
                filename,
                username,
                controller,
                dataset,
            )

            # An exception from this point on MAY leave an uploaded tar file
            # (possibly partial, or corrupted); remove it if possible on
            # error recovery.
            recovery.add(tar_full_path.unlink, "delete tarball")

            with tar_full_path.open(mode="wb") as ofp:
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
                        raise CleanupTime(
                            HTTPStatus.INSUFFICIENT_STORAGE,
                            f"Out of space on {tar_full_path.root}",
                        )
                    else:
                        raise CleanupTime(
                            HTTPStatus.INTERNAL_SERVER_ERROR,
                            "Unexpected error encountered during file upload",
                        )
                except Exception:
                    raise CleanupTime(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        "Unexpected error encountered during file upload",
                    )

                if bytes_received != content_length:
                    raise CleanupTime(
                        HTTPStatus.BAD_REQUEST,
                        f"Expected {content_length} bytes but received {bytes_received} bytes",
                    )
                elif hash_md5.hexdigest() != md5sum:
                    raise CleanupTime(
                        HTTPStatus.BAD_REQUEST,
                        f"MD5 checksum {hash_md5.hexdigest()} does not match expected {md5sum}",
                    )

                # First write the .md5
                self.logger.info("Creating MD5 file {}: {}", md5_full_path, md5sum)

                # From this point attempt to remove the MD5 file on error exit
                recovery.add(md5_full_path.unlink, "remove MD5 file")
                try:
                    md5_full_path.write_text(f"{md5sum} {filename}\n")
                except Exception:
                    raise CleanupTime(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        f"Failed to write .md5 file '{md5_full_path}'",
                    )

                # Create a file tree object
                try:
                    file_tree = FileTree(self.config, self.logger)
                    self.logger.info(
                        "Created {} of type {}", file_tree, type(file_tree)
                    )
                except Exception:
                    raise CleanupTime(
                        HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to map the file tree"
                    )

                # Move the files to their final location
                try:
                    tarball = file_tree.create(controller, tar_full_path)
                except Exception:
                    raise CleanupTime(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        "Unable to create dataset in file system",
                    )

            self.finalize_dataset(dataset, tarball, self.config, self.logger)
        except Exception as e:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            abort_msg = "INTERNAL ERROR"
            if isinstance(e, CleanupTime):
                cause = e.__cause__ if e.__cause__ else e.__context__
                if e.status == HTTPStatus.INTERNAL_SERVER_ERROR:
                    log_func = self.logger.exception if cause else self.logger.error
                    log_func(
                        "{}:{}:{} error {}", username, controller, filename, e.message,
                    )
                else:
                    self.logger.warning(
                        "{}:{}:{} error {} ({})",
                        username,
                        controller,
                        filename,
                        e.message,
                        cause,
                    )
                    abort_msg = e.message
                status = e.status
            else:
                self.logger.exception("Unexpected exception in outer try")
            recovery.cleanup()
            abort(status, message=abort_msg)

        response = jsonify(dict(message="File successfully uploaded"))
        response.status_code = HTTPStatus.CREATED
        return response

    @staticmethod
    def finalize_dataset(
        dataset: Dataset, tarball: Tarball, config: PbenchServerConfig, logger: Logger
    ):
        try:
            dataset.advance(States.UPLOADED)

            # TODO: Implement per-user override of default (requires PR #2049)
            try:
                retention_days = int(
                    config.get_conf(
                        __name__, "pbench-server", "default-dataset-retention-days", 90
                    )
                )
            except Exception as e:
                logger.error("Unable to get integer retention days: {}", str(e))
                raise
            retention = datetime.timedelta(days=retention_days)
            deletion = datetime.datetime.now() + retention
            Metadata.setvalue(
                dataset=dataset,
                key=Metadata.TARBALL_PATH,
                value=str(tarball.tarball_path),
            )
            Metadata.setvalue(
                dataset=dataset, key=Metadata.DELETION, value=f"{deletion:%Y-%m-%d}"
            )
        except Exception as exc:
            logger.error("Unable to finalize {}, '{}'", dataset, exc)
            raise

    @staticmethod
    def supported_file_extension(filename: str) -> bool:
        """Check if the given file name ends with the allowed extension.

        Return True if the allowed extension is found, False otherwise.
        """
        return filename.endswith(Upload.ALLOWED_EXTENSION)
