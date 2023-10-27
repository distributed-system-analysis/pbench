# `GET|PUT /api/v1/datasets/<dataset>/metadata`

This API sets or retrieves metadata for the identified dataset. For `GET` you
specify a list of metadata keys with the `?metadata` query parameter; for `PUT`
you specify an `application/json` request body to specify a set of keys and
values.

## URI parameters

`<dataset>` string \
The resource ID of a dataset on the Pbench Server.

## Query parameters

`metadata` (`GET` only) \
A list of metadata keys to retrieve. For example, `?metadata=dataset,global,server,user`
will retrieve all metadata values, each namespace as a nested JSON object. (This can
be a lot of data, and is generally not recommended.)

The metadata query string `?metadata=dataset.name,dataset.access,server` will return
an `application/json` response something like this:

```json
{
    "dataset.access": "public",
    "dataset.name": "uperf__2023.08.21T15.09.46",
    "server": {
        "benchmark": "uperf",
        "deletion": "2025-08-21",
        "tarball-path": "<internal path>"
    }
}
```
## Request body

For `PUT`, specify the keys and values in an `application/json` request body
under the `"metadata"` field, like this:

```json
{
  "metadata": {
    "dataset.name": "I shall call you squishie",
    "server.deletion": "2024-12-13",
    "global.pbench": {
      "tag": "ABC",
      "version": 1.0
    }
  }
}
```

## Request headers

`authorization: bearer` token \
*Bearer* schema authorization is required to update a dataset.
E.g., `authorization: bearer <token>`

## Response headers

`content-type: application/json` \
The return is a serialized JSON object with with the retrieved metadata key and
value pairs.

## Resource access

* `GET` requires `READ` access to the `<dataset>` resource, while `PUT` requires
`UPDATE` access to the `<dataset>` resource.

See [Access model](../access_model.md)

## Response status

`200`   **OK** \
Successful request.

`401`   **UNAUTHORIZED** \
The client is not authenticated for a `PUT` call.

`403`   **FORBIDDEN** \
The authenticated client does not have `READ` access (for `GET`) or `UPDATE`
access (for `PUT`) to the specified dataset.

`404`   **NOT FOUND** \
The `<dataset>` resource ID does not exist.

`503`   **SERVICE UNAVAILABLE** \
The server has been disabled using the `server-state` server configuration
setting in the [server configuration](./server_config.md) API. The response
body is an `application/json` document describing the current server state,
a message, and optional JSON data provided by the system administrator.

## Response body

The `application/json` response shows the referenced metadata key values.

For `GET`, these are the keys you specified with the `?metadata`
query parameter.

For `PUT`, the actual metadata values you set are returned, along with a
possible map of errors. In general these are exactly what you set, but
some like `server.archiveonly` and `server.deletion` may be normalized
during validation. For example, for

```
PUT /api/v1/datasets/<resource_id>/metadata
{
  "metadata": {
    "server.archiveonly": "true",
    "server.deletion": "2023-12-25T15:43"
  }
}
```

The response might be:

```json
{
    "errors": {},
    "metadata": {
        "server.archiveonly": true,
        "server.deletion": "2023-12-26"
    }
}
```
