# `GET /api/v1/datasets`

This API returns an `application/json` document describing a filtered
collection of datasets accessible to the client. (An unauthenticated client
can only list `public` datasets.)

The collection of datasets may be filtered by `owner`, `access`, `name`
substring, by date range, or by arbitrary metadata using the query parameters.

Large collections can be paginated for efficiency using the `limit` and `offset`
query parameters.

## Query parameters

`access`    string \
Select whether only `private` or only `public` access datasets will be included
in the list. By default, all datasets readable by the authenticated user are
included. For example, without constraints `/datasets/list` for an authenticated
user will include all `public` datasets plus all datasets owned by the
authenticated user; specifying `private` will show only the authenticated user's
private datasets, while specifying `public` will show only `public` datasets
(regardless of ownership).

`end` date/time \
Select only datasets created on or before the specified time. Time should be
specified in ISO standard format, as `YYYY-MM-DDThh:mm:ss.ffffff[+|-]HH:MM`.
If the timezone offset is omitted it will be assumed to be UTC (`+00:00`); if
the time is omitted it will be assumed as midnight (`00:00:00`) on the
specified date.

`filter` metadata filtering \
Select datasets matching the metadata expressions specified via `filter`
query parameters. Each expression is the name of a metadata key (for example,
`dataset.name`), followed by a colon (`:`) and the comparison string. The
comparison string may be prefixed with a tilda (`~`) to make it a partial
("contains") comparison instead of an exact match. For example,
`dataset.name:foo` looks for datasets with the name "foo" exactly, whereas
`dataset.name:~foo` looks for datasets with a name containing the substring
"foo".

These may be combined across multiple `filter` query parameters or as
comma-separated lists in a single query parameter. Multiple filter expressions
form an `AND` expression, however consecutive filter expressions can be joined
in an `OR` expression by using the circumflex (`^`) character prior to each.
(The first expression with `^` begins an `OR` list while the first subsequent
expression outout `^` ends the `OR` list and is combined with an `AND`.)

For example,
- `filter=dataset.name:a,server.origin:EC2` returns datasets with a name of
"a" and an origin of "EC2".
- `filter=dataset.name:a,^server.origin:EC2,^dataset.metalog.pbench.script:fio` returns datasets with a name of "a" and *either* an origin of "EC2" or generated from the "pbench-fio" script.

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

`offset` integer \
"Paginate" the selected datasets by skipping the first `offset` datasets that
would have been selected by the other query terms. This can be used with
`limit` to progress through the full list in smaller chunks either to assist
with a paginated display or to limit data transfer requirements.

`owner` string \
Select only datasets owned by the specified username. Unless the username
matches the authenticated user, only "public" datasets can be selected.

`start` date/time \
Select only datasets created on or after the specified time. Time should be
specified in ISO standard format, as `YYYY-MM-DDThh:mm:ss.ffffff[+|-]HH:MM`.
If the timezone offset is omitted it will be assumed to be UTC (`+00:00`); if
the time is omitted it will be assumed as midnight (`00:00:00`) on the
specified date.

`keysummary` boolean \
Instead of displaying a list of selected datasets and metadata, use the set of
specified filters to accumulate a nested report on the metadata key namespace
for the set of datasets. See [metadata](../metadata.md) for deails on the
Pbench Server metadata namespaces. Because the `global` and `user` namespaces
are completely dynamic, and the `dataset.metalog` sub-namespace varies greatly
across Pbench Agent benchmark scripts, this mode provides a mechanism for a
metadata visualizer to understand what's available for a set of datasets.

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
by `owner` or `access=private`.

`403`   **FORBIDDEN** \
The client asked to filter `access=private` datasets for an `owner` for which
the client does not have READ access.

`503`   **SERVICE UNAVAILABLE** \
The server has been disabled using the `server-state` server configuration
setting in the [server configuration](./server_config.md) API. The response
body is an `application/json` document describing the current server state,
a message, and optional JSON data provided by the system administrator.

## Response body

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
`GET http://host/api/v1/datasets/list?metadata=user.dashboard.favorite&limit=3`
might return:

```json
{
    "next_url": "http://pbench.example.com/api/v1/datasets?limit=3&metadata=user.dashboard.favorite&offset=3",
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

When the `keysummary` query parameter is `true` (e.g., either `?keysummary` or `?keysummary=true`),
instead of reporting a list of datasets and metadata for each dataset, report a hierarchical
representation of the aggregate metadata namespace across all selected datasets. This returns much
less data and is not subject to pagination.

"Leaf" nodes in the metadata tree are represented by `null` values while any key with children will
be represented as a nested JSON object showing those child keys. That is, the example below shows
that the selected datasets include keys like `dataset.access`, `dataset.metalog.controller.hostname`.

Any of the partial or complete key paths represented here are valid targets for metadata queries.
Since filters (e.g., `GET /api/v1/datasets?filter=xxx`) are always *string* comparisons, it's best
to match leaf node values.

```json
{
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
        "index-map": {
            "container-pbench.v6.run-data.2023-03": null,
            "container-pbench.v6.run-toc.2023-03": null
        },
        "origin": null,
        "tarball-path": null
    }
}
```
