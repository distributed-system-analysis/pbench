from http import HTTPStatus
from typing import Any
from urllib.parse import urlencode, urlparse

from flask import current_app
from flask.json import jsonify
from flask.wrappers import Request, Response
from sqlalchemy import and_, asc, Boolean, cast, desc, func, Integer, or_, String
from sqlalchemy.exc import ProgrammingError, StatementError
from sqlalchemy.orm import aliased, Query
from sqlalchemy.sql.expression import Alias, BinaryExpression, ColumnElement

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
    convert_boolean,
    convert_date,
    convert_int,
    convert_string,
    Parameter,
    ParamType,
    Schema,
    Term,
    Type,
)
import pbench.server.auth.auth as Auth
from pbench.server.database.database import Database
from pbench.server.database.models import TZDateTime
from pbench.server.database.models.datasets import (
    Dataset,
    Metadata,
    MetadataBadKey,
    MetadataError,
)
from pbench.server.database.models.users import User

"""Associate the name of a filter type to the Type record describing it."""
TYPES = {
    "bool": Type(Boolean, convert_boolean),
    "date": Type(TZDateTime, convert_date),
    "int": Type(Integer, convert_int),
    "str": Type(String, convert_string),
}


"""Define the set of operators we allow in query filters.

This maps a symbolic name to a SQLAlchemy filter method on the column.
"""
OPERATORS = {
    "~": "contains",
    "=": "__eq__",
    "<": "__lt__",
    ">": "__gt__",
    "<=": "__le__",
    ">=": "__ge__",
    "!=": "__ne__",
}


def make_operator(
    expression: ColumnElement, operator: str, value: Any
) -> BinaryExpression:
    """Return the SQLAlchemy operator method of a column or JSON expression.

    Args:
        expression: A SQLAlchemy expression or column
        operator: The operator prefix
        value: The value to be compared against

    Returns:
        A SQLAlchemy filter expression.
    """
    return getattr(expression, OPERATORS[operator])(value)


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
        self, query: Query, json: JSON, raw_params: ApiParams, url: str
    ) -> tuple[list[JSONOBJECT], dict[str, str]]:
        """Helper function to return a slice of datasets (constructed according
        to the user specified limit and an offset number) and a paginated object
        containing next page url and total items count.

        E.g. specifying the following limit and offset values will result in the
        corresponding dataset slice:

            "limit": 10, "offset": 20 -> dataset[20: 30]
            "limit": 10 -> dataset[0: 10]
            "offset": 20 -> dataset[20: total_items_count]

        Args:
            query: A SQLAlchemy query object
            json: The query parameters in normalized JSON form
            raw_params: The original API parameters for reference
            url: The API URL

        Returns:
            The list of Dataset objects matched by the query and a pagination
            framework object.
        """
        paginated_result = {}
        query = query.distinct()

        Database.dump_query(query, current_app.logger)

        # This is the first actual query: so if we've constructed a query that
        # the DB engine can't handle, we'll fail here. Try to report as much
        # detail as possible in the log.
        try:
            total_count = query.count()
        except Exception as e:
            try:
                q = str(query.statement.compile(compile_kwargs={"literal_binds": True}))
                msg = f"problem executing {q!r}: {str(e)!r}"
            except Exception as uhoh:
                msg = f"Unable to compile query for {json} -> {str(uhoh)!r} after {str(e)!r}"
            raise APIInternalError(msg)

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

        items = query.all()
        raw = raw_params.query.copy()
        next_offset = offset + len(items)
        if next_offset < total_count:
            json["offset"] = str(next_offset)
            raw["offset"] = str(next_offset)
            parsed_url = urlparse(url)
            next_url = parsed_url._replace(query=urlencode_json(json)).geturl()
        else:
            if limit:
                raw["offset"] = str(total_count)
            next_url = ""

        paginated_result["parameters"] = raw
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

        Specify the value to match separated from the key path by a `:`
        character, e.g., "dataset.name:fio". By default this produces an exact
        match expression as an AND (required) term in the query: only datasets
        with the exact name "fio" will be returned.

        The value may be prefixed by an optional operator in order to perform a
        comparison other than strict equality:

        =   Look for matches strictly equal to the specified value (default)
        ~   Look for matches containing the specified value as a substring
        >   Look for matches strictly greater than the specified value
        <   Look for matches strictly less than the specified value
        >=  Look for matches greater than or equal to the specified value
        <=  Look for matches less than or equal to the specified value
        !=  Look for matches not equal to the specified value

        After the value, you can optionally specify a type for the comparison.
        Note that an incompatible type (other than the default "str") for a
        primary "dataset" column will be rejected, but general Metadata
        (including "dataset.metalog") is stored as generic JSON and the API
        will attempt to cast the selected data to the specified type.

        str     Perform a string match
        int     Perform an integer match
        bool    Perform a boolean match (boolean values are t[rue], f[alse],
                y[es], and n[o])
        date    Perform a date match: the selected key value (and supplied
                filter value) must be strings representing a date-time, ideally
                in ISO-8601 format. UTC is assumed if no timezone is specified.

        For example

            dataset.uploaded:>2023-05-01:date
            global.dashboard.seen:t:bool
            dataset.metalog.pbench.script:!=fio

        To produce an OR (optional) filter term, you can prefix the `key:value`
        with the caret (^) character. Adjacent OR terms will be combined in a
        subexpression, and will match if any of the alternatives matches. For
        example, "^dataset.name:~fio,^dataset.name:~linpack" will match any
        dataset where the name contains either "linpack" or "fio" as a
        substring.

        AND and OR terms can be chained by ordering them:

            "dataset.name:~fio,^global.dashboard.saved:true:bool,
            ^user.dashboard.favorite:true:bool,server.origin:RIYA"

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
            term = Term(
                term=kw,
                types=TYPES,
                operators=OPERATORS,
                default_type="str",
                default_operator="=",
            ).parse_expression()
            combine_or = term.chain == "^"
            keys = term.key.split(".")
            native_key = keys.pop(0).lower()
            vtype = term.type
            value = TYPES[vtype].convert(term.value, None)
            filter = None

            if native_key == Metadata.DATASET:
                second = keys[0].lower()
                # The dataset namespace requires special handling because
                # "dataset.metalog" is really a special native key space
                # named "metalog", while other "dataset" sub-keys are primary
                # columns in the Dataset table.
                if second == Metadata.METALOG:
                    native_key = keys.pop(0).lower()
                elif second == "owner":
                    filter = make_operator(User.username, term.operator, value)
                else:
                    try:
                        c = getattr(Dataset, second)
                        if vtype == "str" and not isinstance(c.type, String):
                            column = cast(getattr(Dataset, second), String)
                        else:
                            if not isinstance(c.type, TYPES[vtype].sqltype):
                                raise APIAbort(
                                    HTTPStatus.BAD_REQUEST,
                                    f"Filter of type {vtype!r} is not compatible with key 'dataset.{c.name}'",
                                )
                            column = c
                    except AttributeError as e:
                        raise APIAbort(
                            HTTPStatus.BAD_REQUEST, str(MetadataBadKey(term.key))
                        ) from e
                    filter = make_operator(column, term.operator, value)
            elif native_key == Metadata.USER:
                # The user namespace requires special handling because the
                # values are always qualified by the owning user rather than
                # only the parent dataset. We need to add a `user_id` term, and
                # if we don't have one then we can't perform the query.
                if not user_id:
                    raise APIAbort(
                        HTTPStatus.UNAUTHORIZED,
                        f"Metadata key {term.key} cannot be used by an unauthenticated client",
                    )

            # NOTE: We don't want to *evaluate* the filter expression here, so
            # check explicitly for None. I.e., "we have no filter" rather than
            # "the evaluated result of this filter is falsey".
            if filter is None:
                expression = aliases[native_key].value[keys].as_string()
                expression = expression.cast(TYPES[vtype].sqltype)
                filter = make_operator(expression, term.operator, value)

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

        results = query.all()
        for result in results:
            # NOTE: to allow sorting by User.username, our query is defined to
            # return (Dataset, User), so we need to isolate the Dataset from
            # the tuple.
            dataset = result[0]
            if not aggregate:
                columns = {c.name: None for c in Dataset.__table__._columns}
                columns["owner"] = None
                aggregate.update({"dataset": columns})
            for m in dataset.metadatas:
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
        self,
        request: Request,
        aliases: dict[str, Any],
        json: JSONOBJECT,
        raw_params: ApiParams,
        query: Query,
    ) -> JSONOBJECT:
        """Gather and paginate the selected datasets

        Run the query we've compiled, with pagination limits applied; collect
        results into a list of JSON objects including selected metadata keys.

        Args:
            request: The HTTP Request object
            aliases: Map of join column aliases for each Metadata namespace
            json: The JSON query parameters
            raw_params: The original API parameters (used for pagination)
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
                type = "str"
                defaulted_type = True
            else:
                values = sort.split(":", maxsplit=2)
                k = values[0]
                o = values[1]
                type = values[2] if len(values) >= 3 else "str"
                defaulted_type = len(values) < 3
                if o.lower() == "asc":
                    order = asc
                elif o.lower() == "desc":
                    order = desc
                else:
                    raise APIAbort(
                        HTTPStatus.BAD_REQUEST,
                        f"The sort order {o!r} for key {k!r} must be 'asc' or 'desc'",
                    )
                if type not in TYPES:
                    raise APIAbort(
                        HTTPStatus.BAD_REQUEST,
                        f"The sort type must be one of {','.join(TYPES.keys())}",
                    )

            if not Metadata.is_key_path(k, Metadata.METADATA_KEYS, metalog_key_ok=True):
                raise APIAbort(HTTPStatus.BAD_REQUEST, str(MetadataBadKey(k)))
            keys = k.split(".")
            native_key = keys.pop(0).lower()
            sorter = None
            cast_to = TYPES[type].sqltype
            if native_key == Metadata.DATASET:
                second = keys[0].lower()
                # The dataset namespace requires special handling because
                # "dataset.metalog" is really a special native key space
                # named "metalog", while other "dataset" sub-keys are primary
                # columns in the Dataset table.
                if second == Metadata.METALOG:
                    native_key = keys.pop(0).lower()
                elif second == "owner":
                    sorter = order(User.username)
                else:
                    try:
                        c = getattr(Dataset, second)
                    except AttributeError as e:
                        raise APIAbort(
                            HTTPStatus.BAD_REQUEST, str(MetadataBadKey(k))
                        ) from e

                    # For native SQL columns, use the SQL type unless
                    # explicitly overridden.
                    sorter = order(c if defaulted_type else c.cast(cast_to))
            if sorter is None:
                query = query.add_column(
                    cast(aliases[native_key].value[keys].as_string(), cast_to)
                )
                sorter = order(
                    cast(aliases[native_key].value[keys].as_string(), cast_to)
                )
            sorters.append(sorter)

        # Apply our list of sort terms
        query = query.order_by(*sorters)

        try:
            results, paginated_result = self.get_paginated_obj(
                query=query, json=json, raw_params=raw_params, url=request.url
            )
        except (AttributeError, ProgrammingError, StatementError) as e:
            raise APIInternalError(
                f"Constructed SQL for {json} isn't executable"
            ) from e
        except Exception as e:
            raise APIInternalError(f"Unexpected SQL exception: {e}") from e

        keys = json.get("metadata")

        response = []
        for result in results:
            # NOTE: to allow sorting by User.username, our query is defined to
            # return (Dataset, User), so we need to isolate the Dataset from
            # the tuple.
            dataset = result[0]
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
        query = Database.db_session.query(Dataset).add_entity(User)
        for key, table in aliases.items():
            terms = [table.dataset_ref == Dataset.id, table.key == key]
            if key == Metadata.USER:
                if not auth_id:
                    continue
                terms.append(table.user_ref == auth_id)
            query = query.outerjoin(table, and_(*terms))
        query = query.outerjoin(User, User.id == Dataset.owner_id)

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
                    HTTPStatus.UNAUTHORIZED, "'mine' filter requires authentication"
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
            result = self.datasets(request, aliases, json, context["raw_params"], query)
        return jsonify(result)
