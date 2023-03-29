# `DELETE /api/v1/datasets/<dataset>`

This API completely deletes a dataset resource, erasing the dataset resource ID,
the dataset tarball and unpacked artifacts, and all backend data related to the
dataset.

## URI parameters

`<dataset>` string \
The resource ID of a dataset on the Pbench Server.

## Request headers

`authorization: bearer` token \
*Bearer* schema authorization is required to access any non-public dataset.
E.g., `authorization: bearer <token>`

## Response headers

`content-type: application/json` \
The return is a serialized JSON object with status feedback.

## Resource access

* Requires `DELETE` access to the `<dataset>` resource

See [Access model](../access_model.md)

## Response status

`401`   **UNAUTHORIZED** \
The client is not authenticated and does not have `DELETE` access to the specified
dataset.

`403`   **FORBIDDEN** \
The authenticated client does not have `DELETE` access to the specified dataset.

`404`   **NOT FOUND** \
The `<dataset>` resource ID does not exist.

`503`   **SERVICE UNAVAILABLE** \
The server has been disabled using the `server-state` server configuration
setting in the [server configuration](./server_config.md) API. The response
body is an `application/json` document describing the current server state,
a message, and optional JSON data provided by the system administrator.

## Response body

The `application/json` response body consists of a JSON object summarizing the
Elasticsearch index deletion. For example, if the dataset has 9 Elasticsearch
index documents and all are deleted successfully,

```json
{
    "failure": 0,
    "ok": 9
}
```

If the dataset had not been indexed, both numbers will be 0. A non-zero
`"failure"` indicates a partial success, which can be retried.
