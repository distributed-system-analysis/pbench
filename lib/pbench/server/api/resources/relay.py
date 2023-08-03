from http import HTTPStatus

from flask import current_app, Response
from flask.wrappers import Request
import requests

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


class Relay(IntakeBase):
    """Retrieve a dataset from a relay server"""

    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.POST,
                OperationCode.CREATE,
                uri_schema=Schema(Parameter("filename", ParamType.STRING)),
                query_schema=Schema(
                    Parameter("access", ParamType.ACCESS),
                    Parameter("delete", ParamType.BOOLEAN),
                    Parameter(
                        "metadata",
                        ParamType.LIST,
                        element_type=ParamType.STRING,
                        string_list=",",
                    ),
                ),
                audit_type=AuditType.NONE,
                audit_name="relay",
                authorization=ApiAuthorizationType.NONE,
            ),
        )

    def _identify(self, args: ApiParams, request: Request) -> Intake:
        """Identify the tarball to be streamed.

        We get the Relay manifest file location from the "uri" API
        parameter.

        The Relay manifest is an application/json file which contains the
        following required fields:

            uri: The Relay URI of the tarball file
            md5: The tarball's MD5 hash (Pbench Server resource ID)
            name: The original tarball name (with .tar.xz but no path)
            access: The desired Dataset access level (default "private")
            metadata: An optional list of "key:value" metadata strings

        This information will be captured in an Intake instance for use by the
        base class and by the _stream method.

        Args:
            args: API parameters
                URI parameters: the Relay manifest URI
            request: The original Request object containing query parameters

        Returns:
            An Intake object capturing the critical information

        Raises:
            APIAbort on failure
        """
        uri = args.uri["uri"]
        try:
            response = requests.get(uri, headers={"Accept": "application/json"})
        except Exception as e:
            raise APIAbort(
                HTTPStatus.BAD_GATEWAY, f"Unable to connect to manifest URI: {str(e)!r}"
            )
        if not response.ok:
            raise APIAbort(
                HTTPStatus.BAD_GATEWAY,
                f"Relay manifest URI problem: {response.reason!r}",
            )

        try:
            information = response.json()
        except Exception as e:
            raise APIAbort(
                HTTPStatus.BAD_GATEWAY,
                f"Relay URI did not return a JSON manifest: {str(e)!r}",
            ) from e

        try:
            uri = information["uri"]
            md5 = information["md5"]
            name = information["name"]
            access = information.get("access", Dataset.PRIVATE_ACCESS)
            metadata = information.get("metadata", [])
        except KeyError as e:
            raise APIAbort(
                HTTPStatus.BAD_GATEWAY, f"Relay info missing {str(e)!r}"
            ) from e

        # If the API client specified metadata, add it to the manifest
        # metadata list. When the common code processes the list into a dict,
        # any later duplicate keys will override the earlier values.
        metadata += args.query.get("metadata", [])
        return Intake(name, md5, access, metadata, uri)

    def _stream(self, intake: Intake, request: Request) -> Access:
        """Determine how to access the tarball byte stream

        Using the _intake information captured in the Intake instance, perform
        a follow-up GET operation to the URI provided by the Relay config file,
        returning the length header and the IO stream.

        Args:
            intake: The Intake parameters produced by _identify
            request: The Flask request object

        Returns:
            An Access object with the data byte stream and length

        Raises:
            APIAbort on failure
        """
        try:
            response: requests.Response = requests.get(
                url=intake.uri,
                stream=True,
                headers={"Accept": "application/octet-stream"},
            )
        except Exception as e:
            raise APIAbort(
                HTTPStatus.BAD_GATEWAY, f"Unable to connect to results URI: {str(e)!r}"
            )
        if not response.ok:
            raise APIAbort(
                response.status_code,
                f"Unable to retrieve relay tarball: {response.reason!r}",
            )
        try:
            length = int(response.headers["Content-length"])
            return Access(length, response.raw)
        except Exception as e:
            raise APIAbort(
                HTTPStatus.BAD_REQUEST, f"Unable to retrieve relay tarball: {str(e)!r}"
            ) from e

    def _cleanup(self, args: ApiParams, intake: Intake, notes: list[str]):
        """Clean up after a completed upload

        When pulling datasets from a relay, the client can ask that the relay
        files be deleted on successful completion to avoid accumulating storage
        on the relay server.

        We capture all HTTP errors here, since there's not much we can do to
        clean up, and the dataset has already been successfully transferred.
        We just note the problems so they can be investigated.

        Args:
            args: API parameters
            intake: The intake object containing the tarball URI
            notes: A list of error strings to report problems.
        """
        errors = False
        if args.query.get("delete"):
            for uri in (args.uri["uri"], intake.uri):
                reason = None
                try:
                    response = requests.delete(uri)
                    if not response.ok:
                        reason = response.reason
                except ConnectionError as e:
                    reason = str(e)
                if reason:
                    errors = True
                    msg = f"Unable to remove relay file {uri}: {reason!r}"
                    current_app.logger.warning("INTAKE relay {}: {}", intake.name, msg)
                    notes.append(msg)
            if not errors:
                notes.append("Relay files were successfully removed.")

    def _post(self, args: ApiParams, request: Request, context: ApiContext) -> Response:
        """Launch the Relay operation from an HTTP POST"""
        return self._intake(args, request, context)
