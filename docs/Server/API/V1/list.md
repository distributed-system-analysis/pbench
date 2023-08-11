# `GET /api/v1/datasets`

This API returns an `application/json` document describing a filtered
collection of datasets accessible to the client. (An unauthenticated client
can only list datasets with access `public`.)

The collection of datasets may be filtered using any combination of a number
of query parameters, including `owner`, `access`, `name` substring, date range,
and arbitrary metadata filter expressions. The selected datasets may be sorted
by any metadata key value in either ascending or descending order. Multiple
sort parameters will be processed in order.

Large collections can be paginated for efficiency using the `limit` and `offset`
query parameters.

The `keysummary` and `daterange` query parameters (if `true`) select "summary"
modes where aggregate metadata is returned without a list of datasets. These two
may be used together, but cannot be used along with the normal collection list
mode as they aren't subject to pagination.

## Query parameters

`access`    string \
Select whether only `private` or only `public` access datasets will be included
in the list. By default, all datasets readable by the authenticated user are
included. For example, without constraints `/datasets/list` for an authenticated
user will include all `public` datasets plus all datasets owned by the
authenticated user; specifying `private` will show only the authenticated user's
private datasets, while specifying `public` will show only `public` datasets
(regardless of ownership).

`daterange` boolean \
Instead of returning a filtered set of datasets, return only the upload
timestamps of the oldest and most recent datasets in the filtered set. This
may be useful for initializing a date picker. If no datasets are selected by
the specified filters, the `from` and `to` keys (see
[results](#dataset-date-range)) will not be returned.

`end` date/time \
Select only datasets created on or before the specified time. Time should be
specified in ISO standard format, as `YYYY-MM-DDThh:mm:ss.ffffff[+|-]HH:MM`.
If the timezone offset is omitted it will be assumed to be UTC (`+00:00`); if
the time is omitted it will be assumed as midnight (`00:00:00`) on the
specified date.

`filter` metadata filtering \
Select datasets matching the metadata expressions specified via `filter`
query parameters. Each expression has the format `[chain]key:[op]value[:type]`:

* `chain` Prefix an expression with `^` (circumflex) to allow combining a set
of expressions with `OR` rather than the default `AND`.
* `key` The name of a metadata key (for example, `dataset.name`)

* `op` An operator to specify how to compare the key value:

  * `=` (Default) Compare for equality
  * `~` Compare against a substring
  * `>` Greater than
  * `<` Less than
  * `>=` Greater than or equal to
  * `<=` Less than or equal to
  * `!=` Not equal

* `value` The value to compare against. This will be interpreted based on the specified type.
* `type` The string value will be cast to this type. Any value can be cast to
type `str`. General metadata keys (`server`, `global`, `user`, and
`dataset.metalog` namespaces) that have values incompatible with the specified
type will be ignored. If you specify an incompatible type for a primary
`dataset` key, an error will be returned as these types are defined by the
Pbench schema so no match would be possible. (For example, `dataset.name:2:int`
or `dataset.access:2023-05-01:date`.)

  * `str` (Default) Compare as a string
  * `bool` Compare as a boolean
  * `int` Compare as an integer
  * `date` Compare as a date-time string. ISO-8601 recommended, and UTC is
  assumed if no timezone is specified.

For example, `dataset.name:foo` looks for datasets with the name "foo" exactly,
whereas `dataset.name:~foo` looks for datasets with a name containing the
substring "foo".

Multiple expressions may be combined across multiple `filter` query parameters
or as comma-separated lists in a single query parameter. Multiple filter
expressions are combined as an `AND` expression, matching only when all
expressions match. However any consecutive set of expressions starting with `^`
are collected into an "`OR` list" that will be `AND`-ed with the surrounding
terms.

For example,
- `filter=dataset.name:a,server.origin:EC2` returns datasets with a name of
"a" and an origin of "EC2".
- `filter=dataset.name:~andy,^server.origin:EC2,^server.origin:RIYA,
dataset.access:public`
returns only "public" datasets with a name containing the string "andy" which also
have an origin of either "EC2" or "RIYA". As a SQL query, we might write it
as `dataset.name like "%andy%" and (server.origin = 'EC2' or
server.origin = 'RIYA') and dataset.access = 'public'`.

_NOTE_: `filter` expression term values, like the `true` in
`GET /api/v1/datasets?filter=server.archiveonly:true`, are by default
interpreted as strings, so be careful about the string representation of the
value. In this case, `server.archiveonly` is a boolean, which will be matched
as a string value "true" or "false". You can instead specify the expression
term as `server.archiveonly:t:bool` which will treat the specified match value
as a boolean (`t[rue]` or `y[es]` for true, `f[alse]` or `n[o]` for false) and
match against the boolean metadata value.

`keysummary` boolean \
Instead of displaying a list of selected datasets and metadata, use the set of
specified filters to accumulate a nested report on the metadata key namespace
for the set of datasets. See [metadata](../metadata.md) for deails on the
Pbench Server metadata namespaces. Because the `global` and `user` namespaces
are completely dynamic, and the `dataset.metalog` sub-namespace varies greatly
across Pbench Agent benchmark scripts, this mode provides a mechanism for a
metadata visualizer to understand what's available for a set of datasets. If no
datasets are selected by the specified filters, the `keys` key (see
[results](#key-namespace-summary)) will be set to an empty object.

`limit` integer \
"Paginate" the selected datasets by returning at most `limit` datasets. This
can be used in conjunction with `offset` to progress through the full list in
smaller chunks either to assist with a paginated display or to limit data
transfer requirements.

`metadata` list \
Request the named [metadata](../metadata.md) to be returned along with the
resource name and ID. This can be a single metadata key path or comma-separated
list of such strings. The `metadata` query parameter can be repeated. For
example, the following are all equivalent:
* `?metadata=dataset.created,server.deletion,user`
* `?metadata=dataset.created&metadata=dataset.deletion,user`
* `?metadata=dataset.created&metadata=dataset.deletion&metadata=user`

`mine` boolean \
Allows filtering for datasets owned by the authenticated client (if the value
is omitted, e.g., `?mine` or `?mine=true`) or owned by *other* users (e.g.,
`?mine=false`).

`name` string \
Select only datasets with a specified substring in their name. The filter
`?name=fio` is semantically equivalent to `?filter=dataset.name:~fio`.

`offset` integer \
"Paginate" the selected datasets by skipping the first `offset` datasets that
would have been selected by the other query terms. This can be used with
`limit` to progress through the full list in smaller chunks either to assist
with a paginated display or to limit data transfer requirements.

`owner` string \
Select only datasets owned by the specified username. Unless the username
matches the authenticated user, only "public" datasets can be selected.

`sort` sort expression \
Sort the returned datasets by one or more sort expressions. You can separate
multiple expressions using comma lists, or across separate `sort` query
parameters, which will be processed in order. Any Metadata namespace key can
be specified.

Specify a sort order using the keywords `asc` (ascending) or `desc`
(descending), separated from the key name with a colon (`:`). For example,
`dataset.name:asc` or `dataset.metalog.pbench.script:desc`. The default is
"ascending" if no order is specified. If no sort expressions are specified,
datasets are returned sorted by `dataset.resource_id`.

For example, `GET /api/v1/datasets?sort=global.dashboard.seen:desc,dataset.name`
will return selected datasets sorted first in descending order based on whether
the dataset has been marked "seen" by the dashboard, and secondly sorted by the
dataset name. The Pbench Dashboard stores `global.dashboard.seen` as a `boolean`
value, so in this case `true` values will appear before `false` values.

`start` date/time \
Select only datasets created on or after the specified time. Time should be
specified in ISO standard format, as `YYYY-MM-DDThh:mm:ss.ffffff[+|-]HH:MM`.
If the timezone offset is omitted it will be assumed to be UTC (`+00:00`); if
the time is omitted it will be assumed as midnight (`00:00:00`) on the
specified date.

## Request headers

`authorization: bearer` token [_optional_] \
*Bearer* schema authorization is required to access any non-public dataset.
E.g., `authorization: bearer <token>`. If omitted, the client is unauthenticated
and only `public` access datasets will be selected.

## Response headers

`content-type: application/json` \
The return is a serialized JSON object with information about the selected
datasets.

## Resource access

* Only `<dataset>` resources selected by the filter to which the authenticated
user has READ access will be returned.

See [Access model](../access_model.md)

## Response status

`200`   **OK** \
Successful request.

`401`   **UNAUTHORIZED** \
The client did not provide an authentication token but asked to filter datasets
by `owner`, `access=private`, `mine`, or asked for `user` namespace metadata.

`403`   **FORBIDDEN** \
The client asked to filter `access=private` datasets for an `owner` for which
the client does not have READ access.

`503`   **SERVICE UNAVAILABLE** \
The server has been disabled using the `server-state` server configuration
setting in the [server configuration](./server_config.md) API. The response
body is an `application/json` document describing the current server state,
a message, and optional JSON data provided by the system administrator.

## Response body

### Dataset date range

The `application/json` response body is a JSON object describing the earliest
and most recent dataset upload time for the selected list of datasets. If the
collection filters exclude all datasets (the result set is empty), the return
value will be empty, omitting both the `from` and `to` keywords.

```json
{
    "from": "2023-03-17T03:14:02.013184+00:00",
    "to": "2023-04-05T11:29:02.585772+00:00"
}
```

### Dataset list

The `application/json` response body contains a list of objects which describe
the datasets selected by the specified query criteria, along with the total
number of matching datasets and a `next_url` to support pagination.

#### next_url

When pagination is used, this gives the full URI to acquire the next page using
the same `metadata` and `limit` values. The client can simply `GET` this URI for
the next page. When the entire collection has been returned, `next_url` will be
null.

#### total

The total number of datasets matching the filter criteria regardless of the
pagination settings.

#### results

The paginated dataset collection.

Each of these objects contains the following fields:
* `resource_id`: The internal unique ID of the dataset within the Pbench Server.
This value will be used to reference the dataset in most other APIs.
* `name`: The resource name given to the dataset. While this has an initial
default value related to the benchmark script, date, and user configuration
parameters, this value can be changed by the owner of the dataset and is for
display purposes and must not be assumed to be unique or definitive.
* `metadata`: If additional metadata was requested, it will appear as a nested
JSON object in this field.

For example, the query
`GET https://host/api/v1/datasets/list?metadata=user.dashboard.favorite&limit=3`
might return:

```json
{
    "next_url": "https://pbench.example.com/api/v1/datasets?limit=3&metadata=user.dashboard.favorite&offset=3",
    "results": [
        {
            "metadata": {
                "user.dashboard.favorite": null
            },
            "name": "pbench-user-benchmark__2023.03.23T20.26.03",
            "resource_id": "001ab7f04079f620f6f624b6eea913df"
        },
        {
            "metadata": {
                "user.dashboard.favorite": null
            },
            "name": "pbench-user-benchmark__2023.03.18T19.07.42",
            "resource_id": "006fab853eb42907c6c202af1d6b750b"
        },
        {
            "metadata": {
                "user.dashboard.favorite": null
            },
            "name": "fio__2023.03.28T03.58.19",
            "resource_id": "009ad5f818d9a32af6128dd2b0255161"
        }
    ],
    "total": 722
}
```

### Key namespace summary

When the `keysummary` query parameter is `true` (e.g., either `?keysummary` or
`?keysummary=true`), instead of reporting a list of datasets and metadata for
each dataset, the `application/json` response body contains a hierarchical
representation of the aggregate metadata namespace across all selected datasets.
This returns much less data and is not subject to pagination.

"Leaf" nodes in the metadata tree are represented by `null` values while any
key with children will be represented as a nested JSON object showing those
child keys. From the example output below a client can identify many key paths
including `dataset.access` and `dataset.metalog.controller.hostname`.

Any of the partial or complete key paths represented in the output document are
valid targets for metadata queries: for example `dataset.metalog.pbench.script`
is a "leaf" node, but `GET /api/v1/datasets?metadata=dataset.metalog.pbench`
will return a JSON document with the keys `config`, `date`, `hostname_f`,
`hostname_ip`, `hostname_s`, `iterations`, `name`, `rpm-version`, `script`, and
`tar-ball-creation-timestamp`.

```json
{
    "keys": {
        "dataset": {
            "access": null,
            "id": null,
            "metalog": {
                "controller": {
                    "hostname": null,
                    "hostname-alias": null,
                    "hostname-all-fqdns": null,
                    "hostname-all-ip-addresses": null,
                    "hostname-domain": null,
                    "hostname-fqdn": null,
                    "hostname-ip-address": null,
                    "hostname-nis": null,
                    "hostname-short": null,
                    "ssh_opts": null
                },
                "iterations/1-default": {
                    "iteration_name": null,
                    "iteration_number": null,
                    "user_script": null
                },
                "pbench": {
                    "config": null,
                    "date": null,
                    "hostname_f": null,
                    "hostname_ip": null,
                    "hostname_s": null,
                    "iterations": null,
                    "name": null,
                    "rpm-version": null,
                    "script": null,
                    "tar-ball-creation-timestamp": null
                },
                "run": {
                    "controller": null,
                    "end_run": null,
                    "raw_size": null,
                    "start_run": null
                },
                "tools": {
                    "group": null,
                    "hosts": null,
                    "trigger": null
                },
                "tools/dbutenho.bos.csb": {
                    "hostname-alias": null,
                    "hostname-all-fqdns": null,
                    "hostname-all-ip-addresses": null,
                    "hostname-domain": null,
                    "hostname-fqdn": null,
                    "hostname-ip-address": null,
                    "hostname-nis": null,
                    "hostname-short": null,
                    "label": null,
                    "rpm-version": null,
                    "tools": null,
                    "vmstat": null
                },
                "tools/dbutenho.bos.csb/vmstat": {
                    "install_check_output": null,
                    "install_check_status_code": null,
                    "options": null
                }
            },
            "name": null,
            "owner_id": null,
            "resource_id": null,
            "uploaded": null
        },
        "server": {
            "deletion": null,
            "origin": null,
            "tarball-path": null
        }
    }
}
```

### Combining key namespace summary and date range

When both the `keysummary` and `daterange` query parameters are `true`, the
`application/json` response body contains the `from`, `to`, and `keys` key
values. If the selected collection filters produce no results, as with
`daterange` alone, the `from` and `to` keys will be omitted and the value of
`keys` will be an empty object.
