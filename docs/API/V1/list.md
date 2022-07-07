# `GET /api/v1/datasets/list`

This API returns an `application/json` document describing the set of datasets
accessible to the client. (An unauthenticated client can only access "public"
datasets.)

The list of datasets may be further filtered by owner, access, name substring,
or by creation date range using the query parameters.

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

`401`   **UNAUTHORIZED** \
The client did not provide an authentication token but asked to filter datasets
by `owner` or `access=private`.

`403`   **FORBIDDEN** \
The client asked to filter `access=private` datasets for an `owner` for which
the client does not have READ access.

## Response body

The `application/json` response body contains a list of objects which describe
the datasets selected by the specified query criteria.

Each of these objects contains the following fields:
* `resource_id`: The internal unique ID of the dataset within the Pbench Server.
This value will be used to reference the dataset in most other APIs.
* `name`: The resource name given to the dataset. While this has an initial
default value related to the benchmark script, date, and user configuration
parameters, this value can be changed by the owner of the dataset and is for
display purposes and must not be assumed to be unique or definitive.
* `metadata`: If additional metadata was requested, it will appear as a nested
JSON object in this field.

For example, the query `GET http://host/api/v1/datasets/list?metadata=user.favorite`
might return:

```json
[
    {
        "name": "pbench-fio_config_2022-06-29:00:00:00",
        "resource_id": "07f0a9cb817e258a54dbf3444abcd3aa",
        "metadata": {"user.favorite": true}
    },
    {
        "name": "the dataset I created for fun",
        "resource_id": "8322d8043755ccd33dc6d7091d1f9ff9",
        "metadata": {"user.favorite": false}
    }
]
```
