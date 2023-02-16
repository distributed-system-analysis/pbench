from http import HTTPStatus
import logging
from typing import Dict, List, Tuple
from urllib.parse import urlencode, urlparse

from flask import current_app
from flask.json import jsonify
from flask.wrappers import Request, Response
from sqlalchemy import and_, cast, or_, String
from sqlalchemy.exc import ProgrammingError, StatementError
from sqlalchemy.orm import Query

from pbench.server import JSON, OperationCode, PbenchServerConfig
from pbench.server.api.resources import (
    APIAbort,
    ApiAuthorizationType,
    ApiBase,
    ApiContext,
    APIInternalError,
    ApiMethod,
    ApiParams,
    ApiSchema,
    Parameter,
    ParamType,
    Schema,
)
import pbench.server.auth.auth as Auth
from pbench.server.database.database import Database
from pbench.server.database.models.datasets import (
    Dataset,
    Metadata,
    MetadataBadKey,
    MetadataError,
)


def urlencode_json(json: JSON) -> str:
    """We must properly encode the metadata query parameter as a list of keys."""
    new_json = {}
    for k, v in sorted(json.items()):
        new_json[k] = ",".join(v) if k in ["metadata", "key"] else v
    return urlencode(new_json)


class DatasetsList(ApiBase):
    """API class to list datasets based on database metadata."""

    def __init__(self, config: PbenchServerConfig):
        super().__init__(
            config,
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
                    Parameter(
                        "filter",
                        ParamType.LIST,
                        element_type=ParamType.STRING,
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
            "limit": 10 -> dataset[0: 10]
            "offset": 20 -> dataset[20: total_items_count]

        TODO: We may need to optimize the pagination
            e.g Use of unique pointers to record the last returned row and then
            use this pointer in subsequent page request instead of an initial
            start to narrow down the result.
        """
        paginated_result = {}
        query = query.order_by(Dataset.resource_id).distinct()
        total_count = query.count()

        # Shift the query search by user specified offset value,
        # otherwise return the batch of results starting from the
        # first queried item.
        offset = json.get("offset", 0)
        if offset:
            query = query.offset(offset)

        # Get the user specified limit, otherwise return all the items
        limit = json.get("limit")
        if limit:
            query = query.limit(limit)

        # Useful for debugging, but verbose: this displays the fully expanded
        # SQL `SELECT` statement.
        if current_app.logger.isEnabledFor(logging.INFO):
            try:
                current_app.logger.info(
                    "QUERY {}",
                    query.statement.compile(compile_kwargs={"literal_binds": True}),
                )
            except Exception as e:
                current_app.logger.error(
                    "Can't compile statement for {}: {}", json, str(e)
                )

        items = query.all()
        current_app.logger.info(
            "QUERY count {}, limit {}, offset {}", total_count, limit, offset
        )

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
            params : API parameters
            request : The original Request object
            context : API context dictionary

        Returns:
            A JSON response containing the paginated query result
        """
        json = params.query
        current_app.logger.info("Query with {}", json)

        # Get the authenticated user ID, if any
        user_id = Auth.get_current_user_id()

        # Build a SQLAlchemy Query object expressing all of our constraints
        query = Database.db_session.query(Dataset).outerjoin(Metadata)
        if "start" in json and "end" in json:
            query = query.filter(Dataset.uploaded.between(json["start"], json["end"]))
        elif "start" in json:
            query = query.filter(Dataset.uploaded >= json["start"])
        elif "end" in json:
            query = query.filter(Dataset.uploaded <= json["end"])
        if "name" in json:
            query = query.filter(Dataset.name.contains(json["name"]))
        if "filter" in json:
            or_list = []
            and_list = []
            for kw in json["filter"]:
                combine_or = False
                contains = False
                k, v = kw.split(":", maxsplit=1)
                if k.startswith("^"):
                    combine_or = True
                    k = k[1:]
                if v.startswith("~"):
                    contains = True
                    v = v[1:]

                if not Metadata.is_key_path(
                    k, Metadata.METADATA_KEYS, metalog_key_ok=True
                ):
                    raise APIAbort(HTTPStatus.BAD_REQUEST, str(MetadataBadKey(k)))
                keys = k.split(".")
                native_key = keys.pop(0).lower()
                terms = []
                use_dataset = False
                dataset = None
                user_private = None

                if native_key == Metadata.DATASET:
                    second = keys[0].lower()
                    # The dataset namespace requires special handling because
                    # "dataset.metalog" is really a special native key space
                    # named "metalog", while other "dataset" sub-keys are primary
                    # columns in the Dataset table.
                    if second == Metadata.METALOG:
                        native_key = keys.pop(0).lower()
                    else:
                        try:
                            c = getattr(Dataset, second)
                            column = (
                                c
                                if c.type.python_type is str
                                else cast(getattr(Dataset, second), String)
                            )
                        except AttributeError as e:
                            raise APIAbort(
                                HTTPStatus.BAD_REQUEST, str(MetadataBadKey(k))
                            ) from e
                        use_dataset = True
                        terms = [column.contains(v) if contains else column == v]
                elif native_key == Metadata.USER:
                    if not user_id:
                        raise APIAbort(
                            HTTPStatus.UNAUTHORIZED,
                            f"Metadata key {k} cannot be used by an unauthenticated client",
                        )
                    user_private = [Metadata.user_id == user_id]

                if not use_dataset:
                    expression = Metadata.value[keys].as_string()
                    terms = [
                        Metadata.key == native_key,
                        expression.contains(v) if contains else expression == v,
                    ]
                    if user_private:
                        terms.extend(user_private)
                filter = and_(*terms)

                if combine_or:
                    or_list.append(filter)
                else:
                    if or_list:
                        and_list.append(or_(*or_list))
                        or_list.clear()
                    and_list.append(filter)

            if or_list:
                and_list.append(or_(*or_list))

            query = query.filter(and_(*and_list))

        query = self._build_sql_query(json.get("owner"), json.get("access"), query)

        try:
            datasets, paginated_result = self.get_paginated_obj(
                query=query, json=json, url=request.url
            )
        except (AttributeError, ProgrammingError, StatementError) as e:
            raise APIInternalError(
                f"Constructed SQL for {json} isn't executable"
            ) from e
        except Exception as e:
            raise APIInternalError(f"Unexpected SQL exception: {e}") from e

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
                current_app.logger.warning(
                    "Error getting metadata {} for dataset {}: {}", keys, dataset, e
                )
            response.append(d)

        paginated_result["results"] = response
        return jsonify(paginated_result)
