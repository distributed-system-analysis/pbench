from http import HTTPStatus
from typing import Any
from urllib.parse import urlencode, urlparse

from flask import current_app
from flask.json import jsonify
from flask.wrappers import Request, Response
from sqlalchemy import and_, asc, cast, desc, func, or_, String
from sqlalchemy.exc import ProgrammingError, StatementError
from sqlalchemy.orm import aliased, Query
from sqlalchemy.sql.expression import Alias

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
                    Parameter("daterange", ParamType.BOOLEAN),
                    Parameter("keysummary", ParamType.BOOLEAN),
                    Parameter(
                        "metadata",
                        ParamType.LIST,
                        element_type=ParamType.KEYWORD,
                        keywords=Metadata.METADATA_KEYS,
                        key_path=True,
                        string_list=",",
                        metalog_ok=True,
                    ),
                    Parameter(
                        "sort",
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
        query = query.distinct()
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
    def filter_query(
        filters: list[str], aliases: dict[str, Alias], query: Query
    ) -> Query:
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
                    HTTPStatus.BAD_REQUEST, f"filter {kw!r} must have the form 'k:v'"
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
            filter = None

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
                    filter = column.contains(v) if contains else column == v
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

            # NOTE: We don't want to *evaluate* the filter expression here, so
            # check explicitly for None.
            if filter is None:
                expression = aliases[native_key].value[keys].as_string()
                filter = expression.contains(v) if contains else expression == v

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

    def accumulate(self, aggregate: JSONOBJECT, key: str, value: Any):
        """Recursive helper to accumulate the metadata namespace

        Iterate through a list of metadata key/value pairs to construct a
        hierarchical aggregation of all metadata keys across the selected
        datasets. Each key in the hierarchy is represented as a key in a
        nested JSON object. "Leaf" keys have the value None. E.g.,

            {
                "dataset": {"name": None, "metalog": {"pbench": {"script": None}}},
                "server": {"deletion": None, "tarball-path": None},
                "global": {"server": {"legacy": {"sha1": None}}}
            }

        Args:
            aggregate: a JSONOBJECT to update with the recursive key/value
            key: the current metadata key path element
            value: the current metadata key's value
        """
        if isinstance(value, dict):
            p = aggregate.get(key)
            if p is None:
                p = {}
                aggregate[key] = p
            for k, v in value.items():
                self.accumulate(p, k, v)
        elif key not in aggregate:
            aggregate[key] = None

    def keyspace(self, query: Query) -> JSONOBJECT:
        """Aggregate the dataset metadata keyspace

        Run the query we've compiled, and process the metadata collections
        attached to each dataset.

        Args:
            query: The basic filtered SQLAlchemy query object

        Returns:
            The aggregated keyspace JSON object
        """
        Database.dump_query(query, current_app.logger)
        aggregate: JSONOBJECT = {}

        datasets = query.all()
        for d in datasets:
            if not aggregate:
                aggregate.update(
                    {"dataset": {c.name: None for c in Dataset.__table__._columns}}
                )
            for m in d.metadatas:
                # "metalog" is a top-level key in the Metadata schema, but we
                # report it as a sub-key of "dataset".
                if m.key == Metadata.METALOG:
                    self.accumulate(aggregate["dataset"], m.key, m.value)
                else:
                    self.accumulate(aggregate, m.key, m.value)
        return {"keys": aggregate}

    def daterange(self, query: Query) -> JSONOBJECT:
        """Return only the date range of the selected datasets.

        Replace the selected "entities" (normally Dataset columns) with the
        SQL min and max functions on the dataset upload timestamp so that the
        generated SQL query will return a tuple of those two values.

        Args:
            query: The basic filtered SQLAlchemy query object

        Returns:
            The date range of the selected datasets
        """
        results = query.with_entities(
            func.min(Dataset.uploaded), func.max(Dataset.uploaded)
        ).first()

        if results and results[0] and results[1]:
            return {"from": results[0].isoformat(), "to": results[1].isoformat()}
        else:
            return {}

    def datasets(
        self, request: Request, aliases: dict[str, Any], json: JSONOBJECT, query: Query
    ) -> JSONOBJECT:
        """Gather and paginate the selected datasets

        Run the query we've compiled, with pagination limits applied; collect
        results into a list of JSON objects including selected metadata keys.

        Args:
            request: The HTTP Request object
            aliases: Map of join column aliases for each Metadata namespace
            json: The JSON query parameters
            query: The basic filtered SQLAlchemy query object

        Returns:
            The paginated dataset listing
        """

        # Process a possible list of sort terms. By default, we sort by the
        # dataset resource_id.
        sorters = []
        for sort in json.get("sort", ["dataset.resource_id"]):
            if ":" not in sort:
                k = sort
                order = asc
            else:
                k, o = sort.split(":", maxsplit=1)
                if o.lower() == "asc":
                    order = asc
                elif o.lower() == "desc":
                    order = desc
                else:
                    raise APIAbort(
                        HTTPStatus.BAD_REQUEST,
                        f"The sort order {o!r} for key {k!r} must be 'asc' or 'desc'",
                    )

            if not Metadata.is_key_path(k, Metadata.METADATA_KEYS, metalog_key_ok=True):
                raise APIAbort(HTTPStatus.BAD_REQUEST, str(MetadataBadKey(k)))
            keys = k.split(".")
            native_key = keys.pop(0).lower()
            sorter = None
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
                    except AttributeError as e:
                        raise APIAbort(
                            HTTPStatus.BAD_REQUEST, str(MetadataBadKey(k))
                        ) from e
                    sorter = order(c)
            if sorter is None:
                sorter = order(aliases[native_key].value[keys])
            sorters.append(sorter)

        # Apply our list of sort terms
        query = query.order_by(*sorters)

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
            except MetadataError:
                d["metadata"] = None
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
        auth_id = Auth.get_current_user_id()

        # Build a SQLAlchemy Query object expressing all of our constraints

        """SQL notes:

        We want to be able to query across all four metadata key namespaces,
        and a SELECT WHERE clause can only match within individual rows.
        That is, if we look for "value1 = 'a' and value2 = 'b'", we won't
        find a match with a single LEFT JOIN as the matched Metadata is
        distributed across separate rows in the join table.

        The way we get around this is ugly and inflexible, but I'm unable to
        find a better way. We actually JOIN against Metadata four separate
        times; all are constrained by the Dataset foreign key, and each is
        additionally constrained by the primary Metadata.key value. (And the
        "user" namespace is additionally constrained by the authorized user
        ID, and omitted if we're not authenticated.)

        This results in a join table with a JSON value column for each of the
        tables, so that a single SELECT WHERE can match against all four of the
        namespaces on a single row in the join table. In order to be able to
        access the duplicate Metadata.value columns, we first create some
        SQL name aliases. What we'll end up with, before we start adding our
        filters, is something (simplified) like:

        Dataset   mtable        stable      gtable          utable
        --------- ------------- ----------- --------------- --------------
        drb       {             {           {               {
                   "pbench":{    "origin":{  "dashboard":{   "dashboard":{
                   }             }           }               }
                  }             }           }               }
        test      {             {           {               {
                   "pbench":{    "origin":{  "dashboard":{   "dashboard":{
                   }             }           }               }
                  }             }           }               }
        """
        aliases = {
            Metadata.METALOG: aliased(Metadata),
            Metadata.SERVER: aliased(Metadata),
            Metadata.GLOBAL: aliased(Metadata),
            Metadata.USER: aliased(Metadata),
        }
        query = Database.db_session.query(Dataset)
        for key, table in aliases.items():
            terms = [table.dataset_ref == Dataset.id, table.key == key]
            if key == Metadata.USER:
                if not auth_id:
                    continue
                terms.append(table.user_ref == auth_id)
            query = query.outerjoin(table, and_(*terms))

        if "start" in json and "end" in json:
            query = query.filter(Dataset.uploaded.between(json["start"], json["end"]))
        elif "start" in json:
            query = query.filter(Dataset.uploaded >= json["start"])
        elif "end" in json:
            query = query.filter(Dataset.uploaded <= json["end"])
        if "name" in json:
            query = query.filter(Dataset.name.contains(json["name"]))
        if "filter" in json:
            query = self.filter_query(json["filter"], aliases, query)

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
        result = {}
        done = False

        # We can do "keysummary" and "daterange", but, as it makes no real
        # sense to paginate either, we don't support them in combination with
        # a normal list query. So we will perform either/or keysummary and
        # daterange, and acquire a normal list of datasets only if neither was
        # specified.
        if json.get("keysummary"):
            result.update(self.keyspace(query))
            done = True
        if json.get("daterange"):
            result.update(self.daterange(query))
            done = True
        if not done:
            result = self.datasets(request, aliases, json, query)
        return jsonify(result)
