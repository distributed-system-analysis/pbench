from http import HTTPStatus

from flask.json import jsonify
from flask.wrappers import Request, Response

from pbench.server import OperationCode, PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiAuthorizationType,
    ApiBase,
    ApiContext,
    ApiMethod,
    ApiParams,
    ApiSchema,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.database.models.audit import (
    Audit,
    AuditReason,
    AuditSqlError,
    AuditStatus,
    AuditType,
)


class ServerAudit(ApiBase):
    """
    API class to retrieve audit records.
    """

    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.GET,
                OperationCode.READ,
                query_schema=Schema(
                    Parameter("dataset", ParamType.DATASET),
                    Parameter("end", ParamType.DATE),
                    Parameter("name", ParamType.STRING),
                    Parameter("object_id", ParamType.STRING),
                    Parameter("operation", ParamType.KEYWORD, enum=OperationCode),
                    Parameter("reason", ParamType.KEYWORD, enum=AuditReason),
                    Parameter("start", ParamType.DATE),
                    Parameter("status", ParamType.KEYWORD, enum=AuditStatus),
                    Parameter("type", ParamType.KEYWORD, enum=AuditType),
                    Parameter("user", ParamType.USER),
                    Parameter("user_id", ParamType.STRING),
                ),
                authorization=ApiAuthorizationType.ADMIN,
            ),
            always_enabled=True,
        )

    def _get(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """
        Retrieve audit trail records. Each operation that affects a resource
        (create, update, delete) generates two audit records, a BEGIN and
        either SUCCESS, FAILURE, or WARNING. Note that the elapsed time for
        the operation can be computed by comparing the timestamps. Details of
        an update are captured by attributes in the finalization record, along
        with an error "message" on failure.

        GET /api/v1/server/audit?start=2022-08-01
            return all audit records since August 1, 2022

        or

        GET /api/v1/server/audit
            return all audit records

        Args:
            params: API parameters
            request: The original Request object containing query parameters
            context: API context dictionary

        Returns:
            HTTP Response object
        """

        try:
            audits = Audit.query(**params.query)
            return jsonify([a.as_json() for a in audits])
        except AuditSqlError as e:
            raise APIAbort(HTTPStatus.INTERNAL_SERVER_ERROR, str(e)) from e
