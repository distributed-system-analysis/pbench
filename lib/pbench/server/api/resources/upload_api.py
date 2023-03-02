import datetime
import errno
import hashlib
from http import HTTPStatus
import os
from pathlib import Path
import shutil
from typing import Any, Optional

from flask import current_app, jsonify
from flask.wrappers import Request, Response
import humanize

from pbench.common.utils import Cleanup
from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiAuthorizationType,
    ApiBase,
    ApiContext,
    APIInternalError,
    ApiMethod,
    ApiParams,
    ApiSchema,
    Parameter,
    ParamType,
    Schema,
)
import pbench.server.auth.auth as Auth
from pbench.server.cache_manager import CacheManager, DuplicateTarball, MetadataError
from pbench.server.database.models.audit import (
    Audit,
    AuditReason,
    AuditStatus,
    AuditType,
    OperationCode,
)
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetDuplicate,
    DatasetNotFound,
    Metadata,
    MetadataBadValue,
    OperationName,
    OperationState,
)
from pbench.server.sync import Sync
from pbench.server.utils import UtcTimeHelper


class CleanupTime(Exception):
    """
    Used to support handling errors during PUT without constantly testing the
    current status and additional indentation. This will be raised to an outer
    try block when an error occurs.
    """

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message

    def __str__(self) -> str:
        return self.message


class Upload(ApiBase):
    """
    Upload a dataset from an agent. This API accepts a tarball and MD5
    value from a client. After validation, it creates a new Dataset DB
    row describing the dataset, along with some metadata.
    """

    CHUNK_SIZE = 65536

    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.PUT,
                OperationCode.CREATE,
                uri_schema=Schema(Parameter("filename", ParamType.STRING)),
                query_schema=Schema(
                    Parameter("access", ParamType.ACCESS),
                    Parameter(
                        "metadata",
                        ParamType.LIST,
                        element_type=ParamType.STRING,
                        string_list=",",
                    ),
                ),
                audit_type=AuditType.NONE,
                audit_name="upload",
                authorization=ApiAuthorizationType.NONE,
            ),
        )
        self.temporary = config.ARCHIVE / CacheManager.TEMPORARY
        self.temporary.mkdir(mode=0o755, parents=True, exist_ok=True)
        current_app.logger.info(
            "Configured PUT temporary directory as {}", self.temporary
        )

    def _put(self, args: ApiParams, request: Request, context: ApiContext) -> Response:
        """Upload a dataset to the server.

        The client must present an authentication bearer token for a registered
        Pbench Server user.

        We get the requested filename from the URI: /api/v1/upload/<filename>.

        We get the dataset's resource ID (which is the tarball's MD5 checksum)
        from the "content-md5" HTTP header.

        We also check that the "content-length" header value is not 0, and that
        it matches the final size of the uploaded tarball file.

        We expect the dataset's tarball file to be uploaded as a data stream.

        If the new dataset is created successfully, return 201 (CREATED).

        The tarball name must be unique on the Pbench Server. If the name
        given matches an existing dataset, and has an identical MD5 resource ID
        value, return 200 (OK). If the identically named dataset does not have
        the same MD5 resource ID, return 400 and a diagnostic message.

        NOTE: This API audits internally, as we don't know the resource ID or
        name of the dataset until we've processed the parameters. We also
        authenticate internally as we only require that a registered user be
        identified rather than authorizing against an existing resource.

        Args:
            args: API parameters
                URI parameters
                    filename: A filename matching the metadata of the uploaded tarball
                Query parameters
                    access: The desired access policy (default is "private")
                    metadata: Metadata key/value pairs to set on dataset
            request: The original Request object containing query parameters
            context: API context dictionary
        """

        # Used to record what steps have been completed during the upload, and
        # need to be undone on failure
        recovery = Cleanup(current_app.logger)
        audit: Optional[Audit] = None
        username: Optional[str] = None
        access = args.query.get("access", Dataset.PRIVATE_ACCESS)

        # We allow the client to set metadata on the new dataset. We won't do
        # anything about this until upload is successful, but we process and
        # validate it here so we can fail early.
        metadata: dict[str, Any] = {}
        if "metadata" in args.query:
            errors = []
            for kw in args.query["metadata"]:
                # an individual value for the "key" parameter is a simple key:value
                # pair.
                try:
                    k, v = kw.split(":", maxsplit=1)
                except ValueError:
                    errors.append(f"improper metadata syntax {kw} must be 'k:v'")
                    continue
                k = k.lower()
                if not Metadata.is_key_path(k, Metadata.USER_UPDATEABLE_METADATA):
                    errors.append(f"Key {k} is invalid or isn't settable")
                    continue
                try:
                    v = Metadata.validate(dataset=None, key=k, value=v)
                except MetadataBadValue as e:
                    errors.append(str(e))
                    continue
                metadata[k] = v
            if errors:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    "at least one specified metadata key is invalid",
                    errors=errors,
                )

        attributes = {"access": access, "metadata": metadata}
        filename = args.uri["filename"]
        tmp_dir: Optional[Path] = None

        try:
            try:
                authorized_user = Auth.token_auth.current_user()
                user_id = authorized_user.id
                username = authorized_user.username
            except Exception:
                username = None
                user_id = None
                raise CleanupTime(HTTPStatus.UNAUTHORIZED, "Verifying user_id failed")

            if os.path.basename(filename) != filename:
                raise CleanupTime(
                    HTTPStatus.BAD_REQUEST, "Filename must not contain a path"
                )

            if not Dataset.is_tarball(filename):
                raise CleanupTime(
                    HTTPStatus.BAD_REQUEST,
                    f"File extension not supported, must be {Dataset.TARBALL_SUFFIX}",
                )

            try:
                md5sum = request.headers["Content-MD5"]
            except KeyError:
                raise CleanupTime(
                    HTTPStatus.BAD_REQUEST, "Missing required 'Content-MD5' header"
                )
            if not md5sum:
                raise CleanupTime(
                    HTTPStatus.BAD_REQUEST,
                    "Missing required 'Content-MD5' header value",
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

            dataset_name = Dataset.stem(filename)

            # NOTE: we isolate each uploaded tarball into a private MD5-based
            # subdirectory in order to retain the original tarball stem name
            # for the cache manager while giving us protection against multiple
            # tarballs with the same name. (A duplicate MD5 will have already
            # failed, so that's not a concern.)
            try:
                tmp_dir = self.temporary / md5sum
                tmp_dir.mkdir()
            except FileExistsError:
                raise CleanupTime(
                    HTTPStatus.CONFLICT,
                    "Temporary upload directory already exists",
                )
            tar_full_path = tmp_dir / filename
            md5_full_path = tmp_dir / f"{filename}.md5"

            bytes_received = 0
            usage = shutil.disk_usage(tar_full_path.parent)
            current_app.logger.info(
                "{} UPLOAD (pre): {:.3}% full, {} remaining",
                tar_full_path.name,
                float(usage.used) / float(usage.total) * 100.0,
                humanize.naturalsize(usage.free),
            )

            current_app.logger.info(
                "PUT uploading {} for {} to {}", filename, username, tar_full_path
            )

            # Create a tracking dataset object; it'll begin in UPLOADING state
            try:
                dataset = Dataset(
                    owner=authorized_user,
                    name=dataset_name,
                    resource_id=md5sum,
                    access=access,
                )
                dataset.add()
            except DatasetDuplicate:
                current_app.logger.info(
                    "Dataset already exists, user = (user_id: {}, username: {}), file = {!a}",
                    user_id,
                    username,
                    dataset_name,
                )
                try:
                    Dataset.query(resource_id=md5sum)
                except DatasetNotFound:
                    current_app.logger.error(
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
                attributes=attributes,
            )
            recovery.add(dataset.delete)

            # An exception from this point on MAY leave an uploaded tar file
            # (possibly partial, or corrupted); remove it if possible on
            # error recovery.
            recovery.add(tar_full_path.unlink)

            # NOTE: We know that the MD5 is unique at this point; so even if
            # two tarballs with the same name are uploaded concurrently, by
            # writing into a temporary directory named for the MD5 we're
            # assured that they can't conflict.
            try:
                with tar_full_path.open(mode="wb") as ofp:
                    hash_md5 = hashlib.md5()

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
                        f"Unexpected error {exc.errno} encountered during file upload",
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
            current_app.logger.info("Creating MD5 file {}: {}", md5_full_path, md5sum)

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
                cache_m = CacheManager(self.config, current_app.logger)
            except Exception:
                raise CleanupTime(
                    HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to map the cache manager"
                )

            # Move the files to their final location
            try:
                tarball = cache_m.create(tar_full_path)
            except DuplicateTarball:
                raise CleanupTime(
                    HTTPStatus.BAD_REQUEST,
                    f"A tarball with the name {dataset_name!r} already exists",
                )
            except MetadataError as exc:
                raise CleanupTime(
                    HTTPStatus.BAD_REQUEST,
                    f"Tarball {dataset.name!r} is invalid or missing required metadata.log: {exc}",
                )
            except Exception as exc:
                raise CleanupTime(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"Unable to create dataset in file system for {tar_full_path}: {exc}",
                )

            usage = shutil.disk_usage(tar_full_path.parent)
            current_app.logger.info(
                "{} UPLOAD (post): {:.3}% full, {} remaining",
                tar_full_path.name,
                float(usage.used) / float(usage.total) * 100.0,
                humanize.naturalsize(usage.free),
            )

            # From this point, failure will remove the tarball from the cache
            # manager.
            #
            # NOTE: the Tarball.delete method won't clean up empty controller
            # directories. This isn't ideal, but we don't want to deal with the
            # potential synchronization issues and it'll become irrelevant with
            # the switch to object store. For now we ignore it.
            recovery.add(tarball.delete)

            # Add the processed tarball metadata.log file contents, if any.
            #
            # If we were unable to find or parse the tarball's metadata.log
            # file, construct a minimal metadata context identifying the
            # dataset as a "foreign" benchmark script, and disable indexing,
            # which requires the metadata.
            try:
                metalog = tarball.metadata
                if not metalog:
                    metalog = {"pbench": {"script": "Foreign"}}
                    metadata[Metadata.SERVER_ARCHIVE] = True
                    attributes["missing_metadata"] = True
                Metadata.create(dataset=dataset, key=Metadata.METALOG, value=metalog)
            except Exception as exc:
                raise CleanupTime(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"Unable to create metalog for Tarball {dataset.name!r}: {exc}",
                )

            try:
                retention_days = self.config.default_retention_period
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
                    key=Metadata.SERVER_DELETION,
                    value=UtcTimeHelper(deletion).to_iso_string(),
                )
                f = self._set_dataset_metadata(dataset, metadata)
                if f:
                    attributes["failures"] = f
            except Exception as e:
                raise CleanupTime(
                    HTTPStatus.INTERNAL_SERVER_ERROR, f"Unable to set metadata: {e!s}"
                )

            # Finally, update the operational state and Audit success.
            try:
                # Determine whether we should enable the INDEX operation.
                should_index = not metadata.get(Metadata.SERVER_ARCHIVE, False)
                enable_next = [OperationName.INDEX] if should_index else None
                Sync(current_app.logger, OperationName.UPLOAD).update(
                    dataset=dataset, state=OperationState.OK, enabled=enable_next
                )
                Audit.create(
                    root=audit, status=AuditStatus.SUCCESS, attributes=attributes
                )
            except Exception as exc:
                raise CleanupTime(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"Unable to finalize dataset {dataset}: {exc!s}",
                )
        except Exception as e:
            message = str(e)
            if isinstance(e, CleanupTime):
                status = e.status
            else:
                status = HTTPStatus.INTERNAL_SERVER_ERROR

            # NOTE: there are nested try blocks so we can't be 100% confident
            # here that an audit "root" object was created. We don't audit on
            # header validation/consistency errors caught before we decide that
            # we have a "resource" to track. We won't try to audit failure if
            # we didn't create the root object.
            if audit:
                if status == HTTPStatus.INTERNAL_SERVER_ERROR:
                    reason = AuditReason.INTERNAL
                    audit_msg = "INTERNAL ERROR"
                else:
                    reason = AuditReason.CONSISTENCY
                    audit_msg = message
                Audit.create(
                    root=audit,
                    status=AuditStatus.FAILURE,
                    reason=reason,
                    attributes={"message": audit_msg},
                )
            recovery.cleanup()
            if status == HTTPStatus.INTERNAL_SERVER_ERROR:
                raise APIInternalError(message) from e
            else:
                raise APIAbort(status, message) from e
        finally:
            if tmp_dir:
                try:
                    shutil.rmtree(tmp_dir)
                except Exception as e:
                    current_app.logger.warning("Error removing {}: {}", tmp_dir, str(e))

        response = jsonify(dict(message="File successfully uploaded"))
        response.status_code = HTTPStatus.CREATED
        return response
