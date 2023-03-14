from http import HTTPStatus
from typing import Any
from urllib.parse import urlencode, urlparse

from flask import current_app
from flask.json import jsonify
from flask.wrappers import Request, Response
from sqlalchemy import and_, cast, or_, String
from sqlalchemy.exc import ProgrammingError, StatementError
from sqlalchemy.orm import Query

from pbench.server import JSON, JSONOBJECT, OperationCode, PbenchServerConfig
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
        new_json[k] = ",".join(v) if k in ("metadata", "filter") else v
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
                    # Filter criteria
                    Parameter("mine", ParamType.BOOLEAN),
                    Parameter("name", ParamType.STRING),
                    Parameter("owner", ParamType.USER),
                    Parameter("access", ParamType.ACCESS),
                    Parameter("start", ParamType.DATE),
                    Parameter("end", ParamType.DATE),
                    Parameter(
                        "filter",
                        ParamType.LIST,
                        element_type=ParamType.STRING,
                        string_list=",",
                    ),
                    # Pagination
                    Parameter("offset", ParamType.INT),
                    Parameter("limit", ParamType.INT),
                    # Output control
                    Parameter("keysummary", ParamType.BOOLEAN),
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
    ) -> tuple[list[JSONOBJECT], dict[str, str]]:
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

        Database.dump_query(query, current_app.logger)

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

    @staticmethod
    def filter_query(filters: list[str], query: Query) -> Query:
        """Provide Metadata filtering for datasets.

        Add SQLAlchemy filters to fulfill the intent of a series of filter
        expressions that want to match exactly or in part against a series of
        metadata keys.

        Any metadata key path can be specified across any of the four supported
        metadata namespaces (dataset, server, global, and user). Note that we
        only support string type matching at this point, so in general only
        "leaf nodes" make sense. E.g., to match `global.dashboard.seen` and
        `global.dashboard.saved` you can't use `global.dashboard:{'seen': True,
        'saved': True}` because there's no mechanism to parse JSON expressions.
        This might be added in the future.

        To match against a key value, separate the key path from the value with
        a `:` character, e.g., "dataset.name:fio". This produces an exact match
        expression as an AND (required) term in the query: only datasets with
        the exact name "fio" will be returned.

        To match against a subset of a key value, insert a tilde (~) following
        the `:`, like "dataset.name:~fio". This produces a "contains" filter
        that will match against any name containing the substring "fio".

        To produce an OR (optional) filter term, you can prefix the `key:value`
        with the caret (^) character. Adjacent OR terms will be combined in a
        subexpression, and will match if any of the alternatives matches. For
        example, "^dataset.name:~fio,^dataset.name:~linpack" will match any
        dataset where the name contains either "linpack" or "fio" as a
        substring.

        AND and OR terms can be chained by ordering them:

            "dataset.name:~fio,^global.dashboard.saved:true,
            ^user.dashboard.favorite:true,server.origin:RIYA"

        will match any dataset with a name containing the substring "fio" which
        ALSO has been marked in the dashboard as either "saved" OR (by the
        current authenticated user) as "favorite" AND was marked as originating
        from "RIYA".

        The caller can supply a list of `filter` query parameters and can use
        `,` to separate filter terms within a single string. This has no effect
         on the result. That is,

            "?filter=a.b:c,^b.c:d,^c.d:e"
        and
            "?filter=a.b:c&filter=^b.c:d&filter:^c.d:e"

        result in identical filtering.

        NOTE on implementation:

        SQLAlchemy objects overload most builtin Python operators; and of
        particular note here, we can separate comparison expressions and
        capture them in isolation for combination later. For example, the
        expression "Metadata.user_id == user_id" is not executed immediately;
        it constructs SQLAlchemy expression objects which will be essentially
        compiled into SQL phrases later when the query is executed. Similarly,
        "Metadata.value[("x", "y")]" binds a reference to a second-level JSON
        field, which would be `value["x"]["y"]` in Python. So we can build
        very flexible arrays of AND- and OR- terms and combine them as desired.

        Args:
            filters: A list of filter expressions
            query: the incoming SQLAlchemy Query with filters attached

        Returns:
            An updated query with additional filters attached.
        """

        # Get the authenticated user ID, if any: we only need this for user
        # namespace keys, but we might process more than one so get it here.
        user_id = Auth.get_current_user_id()

        or_list = []
        and_list = []
        for kw in filters:
            combine_or = False
            contains = False
            try:
                k, v = kw.split(":", maxsplit=1)
            except ValueError:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST, f"filter {kw!r} must have the form 'k=v'"
                )
            if k.startswith("^"):
                combine_or = True
                k = k[1:]
            if v.startswith("~"):
                contains = True
                v = v[1:]

            if not Metadata.is_key_path(k, Metadata.METADATA_KEYS, metalog_key_ok=True):
                raise APIAbort(HTTPStatus.BAD_REQUEST, str(MetadataBadKey(k)))
            keys = k.split(".")
            native_key = keys.pop(0).lower()
            terms = []
            use_dataset = False
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
                        try:
                            is_str = c.type.python_type is str
                        except NotImplementedError:
                            is_str = False
                        if is_str:
                            column = c
                        else:
                            column = cast(getattr(Dataset, second), String)
                    except AttributeError as e:
                        raise APIAbort(
                            HTTPStatus.BAD_REQUEST, str(MetadataBadKey(k))
                        ) from e
                    use_dataset = True
                    terms = [column.contains(v) if contains else column == v]
            elif native_key == Metadata.USER:
                # The user namespace requires special handling because the
                # values are always qualified by the owning user rather than
                # only the parent dataset. We need to add a `user_id` term, and
                # if we don't have one then we can't perform the query.
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

        return query.filter(and_(*and_list))

    def accumulate(self, keys: JSONOBJECT, key: str, value: Any):
        """Recursive helper to accumulate the metadata namespace

        Iterate through a list of metadata key/value pairs to construct a
        herarchical aggregation of all metadata keys across the selected
        datasets. Each key in the hierarchy is represented as a key in a
        nested JSON object. "Leaf" keys are represented with empty JSON
        values. E.g.,

            {
                "dataset": {"name": {}, "metalog": {"pbench": {"script": {}}}},
                "server": {"deletion": {}, "tarball-path": {}},
                "global": {"server": {"legacy": {"sha1": {}}}}
            }

        Args:
            keys: a JSONOBJECT to update with the recursive key/value
            key: the current metadata key path element
            value: the current metadata key's value
        """
        if key in keys:
            p = keys[key]
        else:
            p = {}
            keys[key] = p
        if isinstance(value, dict):
            for k, v in value.items():
                self.accumulate(p, k, v)

    def keyspace(self, query: Query) -> JSONOBJECT:
        """Aggregate the dataset metadata keyspace

        Run the query we've compiled, but instead of returning Dataset proxies,
        we only want the metadata key/value pairs we've selected.

        NOTE: In general we expect every dataset to have some metadata; however
        in the event one doesn't, the key and value returned by the joined
        query will be None. We handle this by ignoring those values.

        Args:
            query: The basic filtered SQLAlchemy query object

        Returns:
            The aggregated keyspace JSON object
        """
        keys: JSONOBJECT = {"dataset": {c.name: {} for c in Dataset.__table__._columns}}
        list = query.with_entities(Metadata.key, Metadata.value).all()
        for k, v in list:
            # "metalog" is a top-level key in the Metadata schema, but we
            # report it as a sub-key of "dataset".
            if k == Metadata.METALOG:
                self.accumulate(keys["dataset"], k, v)
            elif k:
                self.accumulate(keys, k, v)
        return keys

    def datasets(self, request: Request, json: JSONOBJECT, query: Query) -> JSONOBJECT:
        """Gather and paginate the selected datasets

        Run the query we've compiled, with pagination limits applied; collect
        results into a list of JSON objects including selected metadata keys.

        Args:
            request: The HTTP Request object
            json: The JSON query parameters
            query: The basic filtered SQLAlchemy query object

        Returns:
            The paginated dataset listing
        """
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
        return paginated_result

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
            query = self.filter_query(json["filter"], query)

        # The "mine" filter allows queries for datasets that are (true) or
        # aren't (false) owned by the authenticated user. In the absense of
        # the "mine" filter, datasets are selected based on visibility to the
        # authenticated user and other explicit filters including "owner" and
        # "access".
        if "mine" in json:
            if "owner" in json:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST,
                    "'owner' and 'mine' filters cannot be used together",
                )
            auth_id = Auth.get_current_user_id()
            if not auth_id:
                raise APIAbort(
                    HTTPStatus.BAD_REQUEST, "'mine' filter requires authentication"
                )
            if json["mine"]:
                owner = auth_id
            else:
                owner = None
                query = query.filter(Dataset.owner_id != auth_id)
        else:
            owner = json.get("owner")
        query = self._build_sql_query(owner, json.get("access"), query)
        if json.get("keysummary"):
            return jsonify(self.keyspace(query))
        else:
            return jsonify(self.datasets(request, json, query))
