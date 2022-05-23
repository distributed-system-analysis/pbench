import logging
from urllib.parse import urlencode, urlparse

from flask.json import jsonify
from flask.wrappers import Request, Response
from sqlalchemy.orm import Query

from pbench.server import JSON, PbenchServerConfig
from pbench.server.api.resources import (
    API_OPERATION,
    ApiBase,
    ParamType,
    Parameter,
    Schema,
)
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import (
    Dataset,
    MetadataError,
)


class DatasetsList(ApiBase):
    """
    API class to list datasets based on PostgreSQL metadata
    """

    def __init__(self, config: PbenchServerConfig, logger: logging.Logger):
        super().__init__(
            config,
            logger,
            Schema(
                Parameter("name", ParamType.STRING),
                Parameter("owner", ParamType.USER),
                Parameter("access", ParamType.ACCESS),
                Parameter("start", ParamType.DATE),
                Parameter("end", ParamType.DATE),
                Parameter("page_no", ParamType.INT),
                Parameter("page_limit", ParamType.INT),
                Parameter(
                    "metadata",
                    ParamType.LIST,
                    element_type=ParamType.KEYWORD,
                    keywords=ApiBase.METADATA,
                    string_list=",",
                ),
            ),
            role=API_OPERATION.READ,
        )

    def get_paginated_obj(self, query: Query, json: JSON, url: str):
        """
        Helper function to return a paginated object containing slice of dataset
        (constructed according to the page limit and a page number), next page url,
        and total items count.
        TODO: There are multiple ways to optimize the functionality
            1. Use of caching mechanism to temporarily store the queried datasets
            instead of querying the database with every page request.
            2. Use of unique pointers to store the last returned row and then use
            this pointer in subsequent page request instead of initial start to
            narrow down the result.
        """
        paginated_result = {}
        total_count = query.count()
        page_limit = json.get(
            "page_limit", int(self.config.server_config.get("page_limit"))
        )
        page_no = json.get("page_no", 1)
        items = (
            query.order_by(Dataset.name)
            .limit(page_limit)
            .offset((page_no - 1) * page_limit)
            .all()
        )
        json["page_no"] = page_no + 1
        parsed_url = urlparse(url)
        if len(items) < page_limit:
            next_url = ""
        else:
            next_url = (
                parsed_url.scheme
                + "://"
                + parsed_url.netloc
                + parsed_url.path
                + "?"
                + urlencode(json)
            )
        paginated_result["next_url"] = next_url
        paginated_result["total"] = total_count
        return items, paginated_result

    def _get(self, json_data: JSON, request: Request) -> Response:
        """
        Get a list of datasets matching a set of criteria.

        NOTE: This does not rely on a JSON payload to identify the dataset and
        desired metadata keys; instead we rely on URI query parameters.

        Args:
            json_data: Ignored because GET has no JSON payload
            request: The original Request object containing query parameters

        GET /api/v1/datasets/list?start=1970-01-01&end=2040-12-31&owner=fred&metadata=dashboard.seen,server.deletion
        """

        # We missed automatic schema validation due to the lack of a JSON body;
        # construct an equivalent JSON body now so we can run it through the
        # validator.
        json = self._validate_query_params(request, self.schema)

        # Validate the authenticated user's authorization for the combination
        # of "owner" and "access".
        self._check_authorization(json.get("owner"), json.get("access"))

        # Build a SQLAlchemy Query object expressing all of our constraints
        query = Database.db_session.query(Dataset)
        if "start" in json and "end" in json:
            self.logger.info("Adding start / end query")
            query = query.filter(Dataset.created.between(json["start"], json["end"]))
        elif "start" in json:
            self.logger.info("Adding start query")
            query = query.filter(Dataset.created >= json["start"])
        elif "end" in json:
            self.logger.info("Adding end query")
            query = query.filter(Dataset.created <= json["end"])
        if "name" in json:
            self.logger.info("Adding name query")
            query = query.filter(Dataset.name.contains(json["name"]))
        query = self._build_sql_query(json, query)

        # Useful for debugging, but verbose: this displays the fully expanded
        # SQL `SELECT` statement.
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "QUERY {}",
                query.statement.compile(compile_kwargs={"literal_binds": True}),
            )

        # Execute the filtered query, sorted by dataset name so we have a
        # consistent and reproducible output to compare.
        datasets, paginated_result = self.get_paginated_obj(
            query=query, json=json, url=request.url
        )

        keys = json.get("metadata")

        response = []
        for dataset in datasets:
            d = {
                "name": dataset.name,
                "run_id": dataset.md5,
            }
            try:
                d["metadata"] = self._get_dataset_metadata(dataset, keys)
            except MetadataError as e:
                self.logger.warning(
                    "Error getting metadata {} for dataset {}: {}", keys, dataset, e
                )
            response.append(d)
        paginated_result["results"] = response

        return jsonify(paginated_result)
