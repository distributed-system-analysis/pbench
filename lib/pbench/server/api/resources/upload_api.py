import datetime
import errno
import hashlib
from http import HTTPStatus
import os
import shutil
from typing import Optional

from flask import jsonify, request
from flask_restful import abort, Resource
import humanize

from pbench.common.utils import Cleanup, validate_hostname
from pbench.server.auth.auth import Auth
from pbench.server.cache_manager import CacheManager
from pbench.server.database.models.audit import (
    Audit,
    AuditReason,
    AuditStatus,
    OperationCode,
)
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetDuplicate,
    DatasetNotFound,
    Metadata,
    States,
)
from pbench.server.database.models.server_config import ServerConfig
from pbench.server.sync import Operation, Sync
from pbench.server.utils import filesize_bytes, UtcTimeHelper


class CleanupTime(Exception):
    """
    Used to support handling errors during PUT without constantly testing the
    current status and additional indentation. This will be raised to an outer
    try block when an error occurs.
    """

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


class Upload(Resource):
    """
    Upload a dataset from an agent. This API accepts a tarball, controller
    name, and MD5 value from a client. After validation, it creates a new
    Dataset DB row describing the dataset, along with some metadata, and it
    creates a pair of files (tarball and MD5 file) within the designated
    controller directory under the configured ARCHIVE file tree.
    """

    CHUNK_SIZE = 65536
    DEFAULT_RETENTION_DAYS = 90

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.max_content_length = filesize_bytes(
            self.config.get_conf(
                __name__, "pbench-server", "rest_max_content_length", self.logger
            )
        )
        self.temporary = config.ARCHIVE / CacheManager.TEMPORARY
        self.temporary.mkdir(mode=0o755, parents=True, exist_ok=True)
        self.logger.info("Configured PUT temporary directory as {}", self.temporary)

    @Auth.token_auth.login_required()
    def put(self, filename: str):
        disabled = ServerConfig.get_disabled()
        if disabled:
            abort(HTTPStatus.SERVICE_UNAVAILABLE, **disabled)

        # Used to record what steps have been completed during the upload, and
        # need to be undone on failure
        recovery = Cleanup(self.logger)
        audit: Optional[Audit] = None

        try:
            try:
                user_id = Auth.token_auth.current_user().id
                username = Auth.token_auth.current_user().username
            except Exception:
                username = None
                raise CleanupTime(HTTPStatus.UNAUTHORIZED, "Verifying user_id failed")

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

            if not Dataset.is_tarball(filename):
                raise CleanupTime(
                    HTTPStatus.BAD_REQUEST,
                    f"File extension not supported, must be {Dataset.TARBALL_SUFFIX}",
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
                    f"'Content-Length' {content_length} must be no greater "
                    f"than {humanize.naturalsize(self.max_content_length)}",
                )

            tar_full_path = self.temporary / filename
            md5_full_path = self.temporary / f"{filename}.md5"
            dataset_name = Dataset.stem(tar_full_path)

            bytes_received = 0
            usage = shutil.disk_usage(tar_full_path.parent)
            self.logger.info(
                "{} UPLOAD (pre): {}% full, {} bytes remaining",
                tar_full_path.name,
                float(usage.used) / float(usage.total) * 100.0,
                usage.free,
            )

            self.logger.info(
                "PUT uploading {}:{} for user = (user_id: {}, username: {}) to {}",
                controller,
                filename,
                user_id,
                username,
                tar_full_path,
            )

            # Create a tracking dataset object; it'll begin in UPLOADING state
            try:
                dataset = Dataset(
                    owner_id=user_id,
                    name=Dataset.stem(tar_full_path),
                    resource_id=md5sum,
                )
                dataset.add()
            except DatasetDuplicate:
                self.logger.info(
                    "Dataset already exists, user = (user_id: {}, username: {}), file = {!a}",
                    user_id,
                    username,
                    dataset_name,
                )
                try:
                    Dataset.query(resource_id=md5sum)
                except DatasetNotFound:
                    self.logger.error(
                        "Duplicate dataset {} for user = (user_id: {}, username: {}) not found",
                        dataset_name,
                        user_id,
                        username,
                    )
                    raise CleanupTime(
                        HTTPStatus.INTERNAL_SERVER_ERROR, "INTERNAL ERROR"
                    )
                else:
                    response = jsonify(dict(message="Dataset already exists"))
                    response.status_code = HTTPStatus.OK
                    return response
            except CleanupTime:
                raise  # Propagate a CleanupTime exception to the outer block
            except Exception:
                raise CleanupTime(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    message="Unable to create dataset",
                )

            audit = Audit.create(
                operation=OperationCode.CREATE,
                name="upload",
                user_id=user_id,
                user_name=username,
                dataset=dataset,
                status=AuditStatus.BEGIN,
            )
            recovery.add(dataset.delete)

            self.logger.info(
                "Uploading file {!a} (user = (user_id: {}, username: {}), ctrl = {!a}) to {}",
                filename,
                user_id,
                username,
                controller,
                dataset,
            )

            # An exception from this point on MAY leave an uploaded tar file
            # (possibly partial, or corrupted); remove it if possible on
            # error recovery.
            recovery.add(tar_full_path.unlink)

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
                recovery.add(md5_full_path.unlink)
                try:
                    md5_full_path.write_text(f"{md5sum} {filename}\n")
                except Exception:
                    raise CleanupTime(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        f"Failed to write .md5 file '{md5_full_path}'",
                    )

            # Create a cache manager object
            try:
                cache_m = CacheManager(self.config, self.logger)
            except Exception:
                raise CleanupTime(
                    HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to map the cache manager"
                )

            # Move the files to their final location
            try:
                tarball = cache_m.create(controller, tar_full_path)
            except Exception:
                raise CleanupTime(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"Unable to create dataset in file system for {tar_full_path}",
                )

            usage = shutil.disk_usage(tar_full_path.parent)
            self.logger.info(
                "{} UPLOAD (post): {}% full, {} bytes remaining",
                tar_full_path.name,
                float(usage.used) / float(usage.total) * 100.0,
                usage.free,
            )

            # From this point, failure will remove the tarball from the cache
            # manager.
            #
            # NOTE: the Tarball.delete method won't clean up empty controller
            # directories. This isn't ideal, but we don't want to deal with the
            # potential synchronization issues and it'll become irrelevant with
            # the switch to object store. For now we ignore it.
            recovery.add(tarball.delete)

            # Now that we have the tarball, extract the dataset timestamp from
            # the metadata.log file.
            #
            # If the metadata.log is missing or corrupt, or doesn't contain the
            # "date" property in the "pbench" section, the resulting exception
            # will cause the upload to fail with an error.
            #
            # NOTE: The full metadata.log (as a JSON object with section names
            # as the top level key) will be stored as a Metadata key using the
            # reserved internal key "metalog". For retrieval, the "dataset" key
            # provides a JSON mapping of the Dataset SQL object, enhanced with
            # the dataset's "metalog" Metadata key value.
            #
            # NOTE: we're setting the Dataset "created" timestamp here, but it
            # won't be committed to the database until the "advance" operation
            # at the end.
            try:
                metadata = tarball.get_metadata()
                dataset.created = UtcTimeHelper.from_string(
                    metadata["pbench"]["date"]
                ).utc_time
                Metadata.create(dataset=dataset, key=Metadata.METALOG, value=metadata)
            except Exception as exc:
                raise CleanupTime(
                    HTTPStatus.BAD_REQUEST,
                    f"Tarball {dataset.name!r} is invalid or missing required metadata.log: {exc}",
                )

            try:
                retention_days = int(
                    self.config.get_conf(
                        __name__,
                        "pbench-server",
                        "default-dataset-retention-days",
                        self.DEFAULT_RETENTION_DAYS,
                    )
                )
            except Exception as e:
                raise CleanupTime(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"Unable to get integer retention days: {e!s}",
                )

            # Calculate a default deletion time for the dataset, based on the
            # time it was uploaded rather than the time it was originally
            # created which might much earlier.
            try:
                retention = datetime.timedelta(days=retention_days)
                deletion = dataset.uploaded + retention
                Metadata.setvalue(
                    dataset=dataset,
                    key=Metadata.TARBALL_PATH,
                    value=str(tarball.tarball_path),
                )
                Metadata.setvalue(
                    dataset=dataset,
                    key=Metadata.DELETION,
                    value=UtcTimeHelper(deletion).to_iso_string(),
                )
            except Exception as e:
                raise CleanupTime(
                    HTTPStatus.INTERNAL_SERVER_ERROR, f"Unable to set metadata: {e!s}"
                )

            # Finally, update the dataset state and commit the `created` date
            # and state change.
            try:
                dataset.advance(States.UPLOADED)
                Sync(self.logger, "upload").update(
                    dataset=dataset, enabled=[Operation.BACKUP, Operation.UNPACK]
                )
                Audit.create(root=audit, status=AuditStatus.SUCCESS)
            except Exception as exc:
                raise CleanupTime(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"Unable to finalize dataset {dataset}: {exc!s}",
                )
        except Exception as e:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            abort_msg = "INTERNAL ERROR"
            if isinstance(e, CleanupTime):
                cause = e.__cause__ if e.__cause__ else e.__context__
                if e.status == HTTPStatus.INTERNAL_SERVER_ERROR:
                    log_func = self.logger.exception if cause else self.logger.error
                    log_func(
                        "{}:{}:{} error {}", username, controller, filename, e.message
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

            # NOTE: there are nested try blocks so we can't be 100% confident
            # here that an audit "root" object was created. We don't audit on
            # header validation/consistency errors caught before we decide that
            # we have a "resource" to track. We won't try to audit failure if
            # we didn't create the root object.
            if audit:
                if status == HTTPStatus.INTERNAL_SERVER_ERROR:
                    reason = AuditReason.INTERNAL
                else:
                    reason = AuditReason.CONSISTENCY
                Audit.create(
                    root=audit,
                    status=AuditStatus.FAILURE,
                    reason=reason,
                    attributes={"message": abort_msg},
                )
            recovery.cleanup()
            abort(status, message=abort_msg)

        response = jsonify(dict(message="File successfully uploaded"))
        response.status_code = HTTPStatus.CREATED
        return response
