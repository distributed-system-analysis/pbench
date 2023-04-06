# `GET /api/v1/datasets/daterange`

This API returns the range of creation dates for all datasets accessible to the
authenticated client, optionally filtered by owner and/or access policy.

For example, this can be used to initialize a date picker.

## Query parameters

`access`    string \
Select whether only `private` or only `public` access datasets will be included
in the list. By default, all datasets readable by the authenticated user are
included. For example, without constraints `/datasets/daterange` for an
authenticated user will include all `public` datasets plus all datasets owned
by the authenticated user; specifying `private` will show only the authenticated
user's private datasets, while specifying `public` will show only `public`
datasets (regardless of ownership).

`owner` string \
Select only datasets owned by the specified username. Unless the username
matches the authenticated user, only "public" datasets can be selected.

## Response status

`200`   **OK** \
Successful request.

`401`   **UNAUTHORIZED** \
The client did not provide an authentication token but asked to filter datasets
by `owner` or `access=private`.

`403`   **FORBIDDEN** \
The client asked to filter `access=private` datasets or by `owner` for which
the client does not have READ access.

`503`   **SERVICE UNAVAILABLE** \
The server has been disabled using the `server-state` server configuration
setting in the [server configuration](./server_config.md) API. The response
body is an `application/json` document describing the current server state,
a message, and optional JSON data provided by the system administrator.

## Response headers

`content-type: application/json` \
The return is a JSON document containing the date range of datasets on the
Pbench Server.

## Response body

The `application/json` response body is a JSON object describing the earliest
and most recent dataset upload time on the Pbench Server.

```json
{
    "from": "2023-03-17T03:14:02.013184+00:00",
    "to": "2023-04-05T11:29:02.585772+00:00"
}
```
