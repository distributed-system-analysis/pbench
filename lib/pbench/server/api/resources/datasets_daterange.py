from logging import Logger
import logging

from flask.json import jsonify
from flask.wrappers import Request, Response
from sqlalchemy import func

from pbench.server import PbenchServerConfig
from pbench.server.api.resources import (
    ApiBase,
    API_OPERATION,
    Parameter,
    ParamType,
    Schema,
)
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import Dataset


class DatasetsDaterange(ApiBase):
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

    def _get(self, _, request: Request) -> Response:
        """
        Get the date range for which datasets are available to the client based
        on authentication plus optional dataset owner and access criteria.

        Args:
            json_data: For a GET, this contains only the Flask URI template
                values, which aren't used here
            request: The original Request object containing query parameters


        GET /api/v1/datasets/daterange?owner=user&access=public
        """

        json = self._collect_query_params(request, self.GET_SCHEMA)
        new_json = self.GET_SCHEMA.validate(json) if json else json

        access = new_json.get("access")
        owner = json.get("owner")
        self.logger.info("Getting date range for user {!r}, access {!r}", owner, access)

        # Validate the authenticated user's authorization for the combination
        # of "owner" and "access".
        self._check_authorization(owner, access)

        # Build a SQLAlchemy Query object expressing all of our constraints
        query = Database.db_session.query(
            func.min(Dataset.created), func.max(Dataset.created)
        )
        query = self._build_sql_query(new_json, query)

        # Useful for debugging, but verbose: this displays the fully expanded
        # SQL `SELECT` statement.
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "QUERY {}",
                query.statement.compile(compile_kwargs={"literal_binds": True}),
            )

        # Execute the query, returning a tuple of the 'min' date and the
        # 'max' date.
        results = query.first()

        self.logger.info("Results: {!r}", results)

        return jsonify({"from": results[0].isoformat(), "to": results[1].isoformat()})
