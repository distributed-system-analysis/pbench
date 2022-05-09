from flask.json import jsonify
from flask.wrappers import Request, Response
from logging import Logger
from sqlalchemy import func

from pbench.server import JSON, PbenchServerConfig
from pbench.server.api.resources import (
    ApiBase,
    API_OPERATION,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Dataset


class DatasetsDateRange(ApiBase):
    """
    API class to retrieve the available date range of accessible datasets.
    """

    GET_SCHEMA = Schema(
        Parameter("owner", ParamType.USER, required=False),
        Parameter("access", ParamType.ACCESS, required=False),
    )

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        super().__init__(
            config,
            logger,
            None,
            role=API_OPERATION.READ,
        )

    def _get(self, json_data: JSON, request: Request) -> Response:
        """
        Get the date range for which datasets are available to the client based
        on authentication plus optional dataset owner and access criteria.

        Args:
            json_data: Ignored because GET has no JSON payload
            request: The original Request object containing query parameters

        GET /api/v1/datasets/daterange?owner=user&access=public
        """

        json = self._validate_query_params(request, self.GET_SCHEMA)
        access = json.get("access")
        owner = json.get("owner")

        # Validate the authenticated user's authorization for the combination
        # of "owner" and "access".
        self._check_authorization(owner, access)

        # Build a SQLAlchemy Query object expressing all of our constraints
        query = Database.db_session.query(
            func.min(Dataset.created), func.max(Dataset.created)
        )
        query = self._build_sql_query(json, query)

        # Execute the query, returning a tuple of the 'min' date and the
        # 'max' date.
        results = query.first()

        return jsonify({"from": results[0].isoformat(), "to": results[1].isoformat()})
