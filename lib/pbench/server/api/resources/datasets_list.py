import logging
from typing import Dict, List, Tuple
from urllib.parse import urlencode, urlparse

from flask.json import jsonify
from flask.wrappers import Request, Response
from sqlalchemy.orm import Query

from pbench.server import JSON, OperationCode
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
from pbench.server.database.models.dataset import Dataset, Metadata, MetadataError
from pbench.server.globals import server


def urlencode_json(json: JSON) -> str:
    """We must properly encode the metadata query parameter as a list of keys."""
    new_json = {}
    for k, v in sorted(json.items()):
        new_json[k] = ",".join(v) if k == "metadata" else v
    return urlencode(new_json)


class DatasetsList(ApiBase):
    """API class to list datasets based on database metadata."""

    endpoint = "datasets_list"
    urls = ["datasets/list"]

    def __init__(self):
        super().__init__(
            ApiSchema(
                ApiMethod.GET,
                OperationCode.READ,
                query_schema=Schema(
                    Parameter("name", ParamType.STRING),
                    Parameter("owner", ParamType.USER),
                    Parameter("access", ParamType.ACCESS),
                    Parameter("start", ParamType.DATE),
                    Parameter("end", ParamType.DATE),
                    Parameter("offset", ParamType.INT),
                    Parameter("limit", ParamType.INT),
                    Parameter(
                        "metadata",
                        ParamType.LIST,
                        element_type=ParamType.KEYWORD,
                        keywords=Metadata.METADATA_KEYS,
                        key_path=True,
                        string_list=",",
                    ),
                ),
                authorization=ApiAuthorizationType.USER_ACCESS,
            ),
        )

    def get_paginated_obj(
        self, query: Query, json: JSON, url: str
    ) -> Tuple[List, Dict[str, str]]:
        """Helper function to return a slice of datasets (constructed according
        to the user specified limit and an offset number) and a paginated object
        containing next page url and total items count.

        E.g. specifying the following limit and offset values will result in the
        corresponding dataset slice:

            "limit": 10, "offset": 20 -> dataset[20: 30]
            "limit": 10               -> dataset[0: 10]
            "offset": 20              -> dataset[20: total_items_count]

        TODO: We may need to optimize the pagination
            e.g Use of unique pointers to record the last returned row and then
            use this pointer in subsequent page request instead of an initial
            start to narrow down the result.
        """
        paginated_result = {}
        total_count = query.count()
        query = query.order_by(Dataset.name)

        # Shift the query search by user specified offset value,
        # otherwise return the batch of results starting from the
        # first queried item.
        offset = json.get("offset", 0)
        query = query.offset(offset)

        # Get the user specified limit, otherwise return all the items
        limit = json.get("limit")
        if limit:
            query = query.limit(limit)

        items = query.all()

        next_offset = offset + len(items)
        if next_offset < total_count:
            json["offset"] = next_offset
            parsed_url = urlparse(url)
            next_url = parsed_url._replace(query=urlencode_json(json)).geturl()
        else:
            next_url = ""

        paginated_result["next_url"] = next_url
        paginated_result["total"] = total_count
        return items, paginated_result

    def _get(
        self, params: ApiParams, request: Request, context: ApiContext
    ) -> Response:
        """Get a list of datasets matching a set of criteria.

        GET /api/v1/datasets/list?start=1970-01-01&end=2040-12-31&owner=fred&metadata=dashboard.seen,server.deletion

        NOTE: This does not rely on a JSON payload to identify the dataset and
        desired metadata keys; instead we rely on URI query parameters.

        Args:
            params: API parameters
            request: The original Request object
            context: API context dictionary

        Returns:
            A JSON response containing the paginated query result
        """
        json = params.query

        # Build a SQLAlchemy Query object expressing all of our constraints
        query = server.db_session.query(Dataset)
        if "start" in json and "end" in json:
            query = query.filter(Dataset.created.between(json["start"], json["end"]))
        elif "start" in json:
            query = query.filter(Dataset.created >= json["start"])
        elif "end" in json:
            query = query.filter(Dataset.created <= json["end"])
        if "name" in json:
            query = query.filter(Dataset.name.contains(json["name"]))
        query = self._build_sql_query(json.get("owner"), json.get("access"), query)

        # Useful for debugging, but verbose: this displays the fully expanded
        # SQL `SELECT` statement.
        if server.logger.isEnabledFor(logging.DEBUG):
            server.logger.debug(
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
                "resource_id": dataset.resource_id,
            }
            try:
                d["metadata"] = self._get_dataset_metadata(dataset, keys)
            except MetadataError as e:
                server.logger.warning(
                    "Error getting metadata {} for dataset {}: {}", keys, dataset, e
                )
            response.append(d)

        paginated_result["results"] = response
        return jsonify(paginated_result)
