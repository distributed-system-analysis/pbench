from http import HTTPStatus

from flask import Response
from flask.wrappers import Request

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiAuthorizationType,
    ApiContext,
    ApiMethod,
    ApiParams,
    ApiSchema,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.api.resources.intake_base import Access, Intake, IntakeBase
from pbench.server.database.models.audit import AuditType, OperationCode
from pbench.server.database.models.datasets import Dataset


class Upload(IntakeBase):
    """Upload a dataset from a client"""

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

    def _prepare(self, args: ApiParams, request: Request) -> Intake:
        """Prepare to begin the intake operation

        We get the filename from the URI: /api/v1/upload/<filename>.

        We get the dataset's resource ID (which is the tarball's MD5 checksum)
        from the "content-md5" HTTP header.

        Args:
            args: API parameters
                URI parameters
                    filename: A filename matching the metadata of the uploaded tarball
                Query parameters
                    access: The desired access policy (default is "private")
                    metadata: Metadata key/value pairs to set on dataset
            request: The original Request object containing query parameters

        Returns:
            An Intake object capturing the critical information
        """

        # Used to record what steps have been completed during the upload, and
        # need to be undone on failure
        access = args.query.get("access", Dataset.PRIVATE_ACCESS)
        filename = args.uri["filename"]

        # We allow the client to set metadata on the new dataset. We won't do
        # anything about this until upload is successful, but we process and
        # validate it here so we can fail early.
        metadata = args.query.get("metadata", [])

        try:
            md5sum = request.headers["Content-MD5"]
        except KeyError:
            raise APIAbort(
                HTTPStatus.BAD_REQUEST, "Missing required 'Content-MD5' header"
            )
        if not md5sum:
            raise APIAbort(
                HTTPStatus.BAD_REQUEST,
                "Missing required 'Content-MD5' header value",
            )

        return Intake(
            name=filename, md5=md5sum, access=access, metadata=metadata, uri=None
        )

    def _access(self, intake: Intake, request: Request) -> Access:
        """Determine how to access the tarball byte stream

        Check that the "content-length" header value is not 0.

        The Flask request object provides the input data stream.

        Args:
            intake: The Intake parameters produced by _intake
            request: The Flask request object

        Returns:
            An Access object with the data byte stream and length
        """
        try:
            length_string = request.headers["Content-Length"]
            content_length = int(length_string)
        except KeyError:
            # NOTE: Werkzeug is "smart" about header access, and knows that
            # Content-Length is an integer. Therefore, a non-integer value
            # will raise KeyError. It's virtually impossible to report the
            # actual incorrect value as we'd just get a KeyError again.
            raise APIAbort(
                HTTPStatus.LENGTH_REQUIRED,
                "Missing or invalid 'Content-Length' header",
            )
        except ValueError:
            # NOTE: Because of the way Werkzeug works, this should not be
            # possible: if Content-Length isn't an integer, we'll see the
            # KeyError. This however serves as a clarifying backup case.
            raise APIAbort(
                HTTPStatus.BAD_REQUEST,
                f"Invalid 'Content-Length' header, not an integer ({length_string})",
            )
        return Access(content_length, request.stream)

    def _put(self, args: ApiParams, request: Request, context: ApiContext) -> Response:
        """Launch the upload operation from an HTTP PUT"""
        return self._intake(args, request, context)
