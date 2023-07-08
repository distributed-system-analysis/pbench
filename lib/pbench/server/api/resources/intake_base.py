from dataclasses import dataclass
import datetime
import errno
import hashlib
from http import HTTPStatus
import os
from pathlib import Path
import shutil
from typing import Any, IO, Optional

from flask import current_app, jsonify
from flask.wrappers import Request, Response
import humanize

from pbench.common.utils import Cleanup
from pbench.server import JSONOBJECT, PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiBase,
    ApiContext,
    APIInternalError,
    ApiParams,
    ApiSchema,
)
import pbench.server.auth.auth as Auth
from pbench.server.cache_manager import CacheManager, DuplicateTarball, MetadataError
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
    MetadataBadValue,
    OperationName,
    OperationState,
)
from pbench.server.sync import Sync
from pbench.server.utils import UtcTimeHelper


@dataclass
class Intake:
    name: str
    md5: str
    access: str
    metadata: list[str]
    uri: Optional[str]


@dataclass
class Access:
    length: int
    stream: IO[bytes]


class IntakeBase(ApiBase):
    """Framework to assimilate a dataset into the Pbench Server.

    This relies on subclasses to provides specific hook methods to identify and
    stream the tarball data:

    _identify: decodes the URI and query parameters to determine the target
        dataset name, the appropriate MD5, the initial access type, and
        optional metadata to be set.
    _stream: decodes the intake data and provides the length and byte IO
        stream to be read into a temporary file.
    """

    CHUNK_SIZE = 65536

    def __init__(self, config: PbenchServerConfig, schema: ApiSchema):
        super().__init__(config, schema)
        self.temporary = config.ARCHIVE / CacheManager.TEMPORARY
        self.temporary.mkdir(mode=0o755, parents=True, exist_ok=True)
        method = list(self.schemas.schemas.keys())[0]
        self.name = self.schemas[method].audit_name
        current_app.logger.info("INTAKE temporary directory is {}", self.temporary)

    @staticmethod
    def process_metadata(metas: list[str]) -> JSONOBJECT:
        """Process 'metadata' query parameter

        We allow the client to set metadata on the new dataset. We won't do
        anything about this until upload is successful, but we process and
        validate it here so we can fail early.

        Args:
            metas: A list of "key:value[,key:value]..." strings)

        Returns:
            A JSON object providing a value for each specified metadata key

        Raises:
            APIAbort on bad syntax or a disallowed metadata key:value pair
        """
        metadata: dict[str, Any] = {}
        errors = []
        for kw in metas:
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
        return metadata

    def _identify(self, args: ApiParams, request: Request) -> Intake:
        """Identify the tarball to be streamed.

        Must be implemented by each subclass of this base class.

        Args:
            args: The API parameters
            request: The Flask request object

        Returns:
            An Intake instance
        """
        raise NotImplementedError()

    def _stream(self, intake: Intake, request: Request) -> Access:
        """Determine how to access the tarball byte stream

        Must be implemented by each subclass of this base class.

        Args:
            intake: The Intake parameters produced by _identify
            request: The Flask request object

        Returns:
            An Access object with the data byte stream and length
        """
        raise NotImplementedError()

    def _intake(
        self, args: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """Common code to assimilate a remote tarball onto the server

        The client must present an authentication bearer token for a registered
        Pbench Server user.

        We support two "intake" modes:

        1) PUT /api/v1/upload/<filename>
        2) POST /api/v1/relay/<uri>

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
        tmp_dir: Optional[Path] = None

        prefix = current_app.server_config.rest_uri
        origin = f"{self._get_uri_base(request).host}{prefix}/datasets/"

        try:
            try:
                authorized_user = Auth.token_auth.current_user()
                user_id = authorized_user.id
                username = authorized_user.username
            except Exception as e:
                username = None
                user_id = None
                raise APIAbort(
                    HTTPStatus.UNAUTHORIZED, "Verifying user_id failed"
                ) from e

            # Ask our helper to determine the name and resource ID of the new
            # dataset, along with requested access and metadata.
            intake = self._identify(args, request)

            filename = intake.name
            metadata = self.process_metadata(intake.metadata)
            attributes = {"access": intake.access, "metadata": metadata}

            if os.path.basename(filename) != filename:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST, "Filename must not contain a path"
                )

            if not Dataset.is_tarball(filename):
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    f"File extension not supported, must be {Dataset.TARBALL_SUFFIX}",
                )

            dataset_name = Dataset.stem(filename)

            # NOTE: we isolate each uploaded tarball into a private MD5-based
            # subdirectory in order to retain the original tarball stem name
            # for the cache manager while giving us protection against multiple
            # tarballs with the same name. (A duplicate MD5 will have already
            # failed, so that's not a concern.)
            try:
                tmp_dir = self.temporary / intake.md5
                tmp_dir.mkdir()
            except FileExistsError as e:
                raise APIAbort(
                    HTTPStatus.CONFLICT,
                    "Temporary upload directory already exists",
                ) from e
            tar_full_path = tmp_dir / filename
            md5_full_path = tmp_dir / f"{filename}.md5"

            bytes_received = 0
            usage = shutil.disk_usage(tar_full_path.parent)
            current_app.logger.info(
                "{} {} (pre): {:.3}% full, {} remaining",
                self.name,
                tar_full_path.name,
                float(usage.used) / float(usage.total) * 100.0,
                humanize.naturalsize(usage.free),
            )

            current_app.logger.info(
                "{} {} for {} to {}", self.name, filename, username, tar_full_path
            )

            # Create a tracking dataset object; it'll begin in UPLOADING state
            try:
                dataset = Dataset(
                    owner=authorized_user,
                    name=dataset_name,
                    resource_id=intake.md5,
                    access=intake.access,
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
                    Dataset.query(resource_id=intake.md5)
                except DatasetNotFound as e:
                    raise APIInternalError(
                        f"Duplicate dataset {intake.md5!r} ({dataset_name!r}) is missing"
                    ) from e
                else:
                    response = jsonify(
                        {
                            "message": "Dataset already exists",
                            "name": dataset_name,
                            "resource_id": intake.md5,
                        }
                    )
                    response.headers["location"] = f"{origin}{intake.md5}/inventory/"
                    response.status_code = HTTPStatus.OK
                    return response
            except APIAbort:
                raise  # Propagate an APIAbort exception to the outer block
            except Exception as e:
                raise APIInternalError("Unable to create dataset") from e

            recovery.add(dataset.delete)

            # AUDIT the operation start before we get any further
            audit = Audit.create(
                operation=OperationCode.CREATE,
                name=self.name,
                user_id=user_id,
                user_name=username,
                dataset=dataset,
                status=AuditStatus.BEGIN,
                attributes=attributes,
            )

            # Now we're ready to pull the tarball, so ask our helper for the
            # length and data stream.
            stream = self._stream(intake, request)

            if stream.length <= 0:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    f"'Content-Length' {stream.length} must be greater than 0",
                )

            # An exception from this point on MAY leave an uploaded tar file
            # (possibly partial, or corrupted); remove it if possible on
            # error recovery.
            recovery.add(lambda: tar_full_path.unlink(missing_ok=True))

            # NOTE: We know that the MD5 is unique at this point; so even if
            # two tarballs with the same name are uploaded concurrently, by
            # writing into a temporary directory named for the MD5 we're
            # assured that they can't conflict.
            try:
                with tar_full_path.open(mode="wb") as ofp:
                    hash_md5 = hashlib.md5()

                    while True:
                        chunk = stream.stream.read(self.CHUNK_SIZE)
                        bytes_received += len(chunk)
                        if len(chunk) == 0 or bytes_received > stream.length:
                            break
                        ofp.write(chunk)
                        hash_md5.update(chunk)
            except OSError as exc:
                # NOTE: Werkzeug doesn't support status 509, so the abort call
                # in _dispatch will fail. Rather than figure out how to fix
                # that, just report as an internal error.
                if exc.errno == errno.ENOSPC:
                    msg = f"Out of space on {tar_full_path.root}"
                else:
                    msg = f"Unexpected error {exc.errno} encountered during file upload"
                raise APIInternalError(msg) from exc
            except Exception as e:
                raise APIInternalError(
                    "Unexpected error encountered during file upload"
                ) from e

            if bytes_received != stream.length:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    f"Expected {stream.length} bytes but received {bytes_received} bytes",
                )
            elif hash_md5.hexdigest() != intake.md5:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    f"MD5 checksum {hash_md5.hexdigest()} does not match expected {intake.md5}",
                )

            # From this point attempt to remove the MD5 file on error exit
            recovery.add(md5_full_path.unlink)
            try:
                md5_full_path.write_text(f"{intake.md5} {filename}\n")
            except Exception as e:
                raise APIInternalError(
                    f"Failed to write .md5 file '{md5_full_path}'",
                ) from e

            # Create a cache manager object
            try:
                cache_m = CacheManager(self.config, current_app.logger)
            except Exception as e:
                raise APIInternalError("Unable to map the cache manager") from e

            # Move the files to their final location
            try:
                tarball = cache_m.create(tar_full_path)
            except DuplicateTarball as exc:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    f"A tarball with the name {dataset_name!r} already exists",
                ) from exc
            except MetadataError as exc:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    f"Tarball {dataset.name!r} is invalid or missing required metadata.log: {exc}",
                ) from exc
            except Exception as exc:
                raise APIInternalError(
                    f"Unable to create dataset in file system for {tar_full_path}: {exc}"
                ) from exc

            usage = shutil.disk_usage(tar_full_path.parent)
            current_app.logger.info(
                "{} {} (post): {:.3}% full, {} remaining",
                self.name,
                tar_full_path.name,
                float(usage.used) / float(usage.total) * 100.0,
                humanize.naturalsize(usage.free),
            )

            # From this point, failure will remove the tarball from the cache
            # manager.
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
                raise APIInternalError(
                    f"Unable to create metalog for Tarball {dataset.name!r}: {exc}"
                ) from exc

            try:
                retention_days = self.config.default_retention_period
            except Exception as e:
                raise APIInternalError(
                    f"Unable to get integer retention days: {e!s}"
                ) from e

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
                raise APIInternalError(f"Unable to set metadata: {e!s}") from e

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
                raise APIInternalError(
                    f"Unable to finalize dataset {dataset}: {exc!s}"
                ) from exc
        except Exception as e:
            if isinstance(e, APIAbort):
                exception = e
            else:
                exception = APIInternalError(str(e))

            # NOTE: there are nested try blocks so we can't be 100% confident
            # here that an audit "root" object was created. We don't audit on
            # header validation/consistency errors caught before we decide that
            # we have a "resource" to track. We won't try to audit failure if
            # we didn't create the root object.
            if audit:
                if exception.http_status == HTTPStatus.INTERNAL_SERVER_ERROR:
                    reason = AuditReason.INTERNAL
                else:
                    reason = AuditReason.CONSISTENCY
                audit_msg = exception.message
                Audit.create(
                    root=audit,
                    status=AuditStatus.FAILURE,
                    reason=reason,
                    attributes={"message": audit_msg},
                )
            recovery.cleanup()
            raise exception from e
        finally:
            if tmp_dir:
                try:
                    shutil.rmtree(tmp_dir)
                except Exception as e:
                    current_app.logger.warning("Error removing {}: {}", tmp_dir, str(e))

        response = jsonify(
            {
                "message": "File successfully uploaded",
                "name": dataset.name,
                "resource_id": dataset.resource_id,
            }
        )
        response.headers["location"] = f"{origin}{dataset.resource_id}/inventory/"
        response.status_code = HTTPStatus.CREATED
        return response
