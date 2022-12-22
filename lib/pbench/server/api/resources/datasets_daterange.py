from flask.json import jsonify
from flask.wrappers import Request, Response
from sqlalchemy import func

from pbench.server import OperationCode, PbenchServerConfig
from pbench.server.api.resources import (
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
from pbench.server.database.database import Database
from pbench.server.database.models.dataset import Dataset


class DatasetsDateRange(ApiBase):
    """
    API class to retrieve the available date range of accessible datasets.
    """

    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
            ApiSchema(
                ApiMethod.GET,
                OperationCode.READ,
                query_schema=Schema(
                    Parameter("owner", ParamType.USER, required=False),
                    Parameter("access", ParamType.ACCESS, required=False),
                ),
                authorization=ApiAuthorizationType.USER_ACCESS,
            ),
        )

    def _get(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """
        Get the date range for which datasets are available to the client based
        on authentication plus optional dataset owner and access criteria.

        Args:
            json_data: Ignored because GET has no JSON payload
            request: The original Request object containing query parameters
            context: API context dictionary

        GET /api/v1/datasets/daterange?owner=user&access=public
        """

        access = params.query.get("access")
        owner = params.query.get("owner")

        # Build a SQLAlchemy Query object expressing all of our constraints
        query = Database.db_session.query(
            func.min(Dataset.created), func.max(Dataset.created)
        )
        query = self._build_sql_query(owner, access, query)

        # Execute the query, returning a tuple of the 'min' date and the
        # 'max' date.
        results = query.first()

        return jsonify({"from": results[0].isoformat(), "to": results[1].isoformat()})
