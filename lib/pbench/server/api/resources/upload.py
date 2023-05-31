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
    """Accept a dataset from a client"""

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

    def _identify(self, args: ApiParams, request: Request) -> Intake:
        """Identify the tarball to be streamed.

        We get the filename from the URI: /api/v1/upload/<filename>.

        We get the dataset's resource ID (which is the tarball's MD5 checksum)
        from the "Content-MD5" HTTP header.

        Args:
            args: API parameters
                URI parameters: filename
                Query parameters: desired access and metadata
            request: The original Request object containing query parameters

        Returns:
            An Intake object capturing the critical information

        Raises:
            APIAbort on failure
        """

        access = args.query.get("access", Dataset.PRIVATE_ACCESS)
        filename = args.uri["filename"]

        # We allow the client to set metadata on the new dataset. We won't do
        # anything about this until upload is successful, but we process and
        # validate it here so we can fail early.
        metadata = args.query.get("metadata", [])

        try:
            md5sum = request.headers["Content-MD5"]
        except KeyError as e:
            raise APIAbort(
                HTTPStatus.BAD_REQUEST, "Missing required 'Content-MD5' header"
            ) from e
        if not md5sum:
            raise APIAbort(
                HTTPStatus.BAD_REQUEST,
                "Missing required 'Content-MD5' header value",
            )

        return Intake(filename, md5sum, access, metadata, uri=None)

    def _stream(self, intake: Intake, request: Request) -> Access:
        """Determine how to access the tarball byte stream

        Check that the "Content-Length" header value is not 0.

        The Flask request object provides the input data stream.

        Args:
            intake: The Intake parameters produced by _identify
            request: The Flask request object

        Returns:
            An Access object with the data byte stream and length

        Raises:
            APIAbort on failure
        """
        try:
            length_string = request.headers["Content-Length"]
            content_length = int(length_string)
        except KeyError as e:
            # NOTE: Werkzeug is "smart" about header access, and knows that
            # Content-Length is an integer. Therefore, a non-integer value
            # will raise KeyError. It's virtually impossible to report the
            # actual incorrect value as we'd just get a KeyError again.
            raise APIAbort(
                HTTPStatus.LENGTH_REQUIRED,
                "Missing or invalid 'Content-Length' header",
            ) from e
        except ValueError as e:
            # NOTE: Because of the way Werkzeug works, this should not be
            # possible: if Content-Length isn't an integer, we'll see the
            # KeyError. This however serves as a clarifying backup case.
            raise APIAbort(
                HTTPStatus.BAD_REQUEST,
                f"Invalid 'Content-Length' header, not an integer ({length_string})",
            ) from e
        return Access(content_length, request.stream)

    def _put(self, args: ApiParams, request: Request, context: ApiContext) -> Response:
        """Launch the upload operation from an HTTP PUT"""
        return self._intake(args, request, context)
