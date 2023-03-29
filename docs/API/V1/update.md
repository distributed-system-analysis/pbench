# `POST /api/v1/datasets/<dataset>?access=<access>&owner=<name>`

This API sets the access and/or name property of the identified dataset. The
specified `<access>` can be either `private` or `public`, or the `access`
query parameter can be omitted to set only the owner. The `<name>` can be
any username know to the Pbench Server, or the `owner` query parameter can
be omitted to set only the access.

## URI parameters

`<dataset>` string \
The resource ID of a dataset on the Pbench Server.

## Query parameters

`access` [`private` | `public` ] \
The desired access scope of the dataset. This requires that the authenticated
user have `UPDATE` access to the dataset. Select `public` to make the dataset
accessible to all clients, or `private` to make the dataset accessible only
to the owner.

`owner` valid username \
A valid Pbench Server username to be given ownership of the specified dataset.
This requires the authenticated user to hold `ADMIN` role, essentially granting
full access to both the current and new owners.

## Request headers

`authorization: bearer` token \
*Bearer* schema authorization is required to access any non-public dataset.
E.g., `authorization: bearer <token>`

## Response headers

`content-type: application/json` \
The return is a serialized JSON object with status feedback.

## Resource access

* Requires `UPDATE` access to the `<dataset>` resource, and, for `owner`, the
`ADMIN` role.

See [Access model](../access_model.md)

## Response status

`200`   **OK** \
Successful request.

`401`   **UNAUTHORIZED** \
The client is not authenticated and does not have `UPDATE`` access to the specified
dataset.

`403`   **FORBIDDEN** \
The authenticated client does not have `UPDATE`` access to the specified dataset.

`404`   **NOT FOUND** \
The `<dataset>` resource ID does not exist.

`503`   **SERVICE UNAVAILABLE** \
The server has been disabled using the `server-state` server configuration
setting in the [server configuration](./server_config.md) API. The response
body is an `application/json` document describing the current server state,
a message, and optional JSON data provided by the system administrator.

## Response body

The `application/json` response body consists of a JSON object summarizing the
Elasticsearch index updates. For example, if the dataset has 9 Elasticsearch
index documents and all are updated successfully,

```json
{
    "failure": 0,
    "ok": 9
}
```

If the dataset had not been indexed, both numbers will be 0. A non-zero
`"failure"` indicates a partial success, which can be retried.
