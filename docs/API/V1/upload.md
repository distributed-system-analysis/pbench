# `PUT /api/v1/upload/<file>`

This API creates a dataset resource by uploading a performance tarball.

Primarily this is expected to be a native Pbench Agent tarball with a specific
structure; however with the `server.archiveonly` metadata key the Pbench Server
can be used to archive and manage metadata for any tarball.

## URI parameters

`<file>` string \
The initial name of the dataset; if `server.archiveonly` is not set, the name must
match the internal name recorded by the Pbench Agent.

## Query parameters

`access` [ `private` | `public` ] \
The desired initial access scope of the dataset. Select `public` to make the dataset
accessible to all clients, or `private` to make the dataset accessible only
to the owner. The default is `private`.

For example, `?access=public`

`metadata` metadata keys \
A valid Pbench Server username to be given ownership of the specified dataset.
This requires the authenticated user to hold `ADMIN` role, essentially granting
full access to both the current and new owners.

In particular the `server.archiveonly` metadata key allows telling the Pbench
Server that the tarball should not be unpacked, analyzed, or indexed, for example
when it doesn't have the expected Pbench Agent `metadata.log`. The tarball will be
archived on the server, and is visible in the dataset collection but won't be indexed.

For example, `?metadata=server.archiveonly:true,global.project:oidc`

## Request headers

`authorization: bearer` token \
*Bearer* schema authorization is required to access any non-public dataset.
E.g., `authorization: bearer <token>`

`content-length` tarball size \
The size of the tarball payload in bytes. Generally supplied automatically by
an upload agent such as Python `requests` or `curl`.

`content-md5` MD5 hash \
The MD5 hash of the compressed tarball file. This must match the actual byte
stream uploaded.

## Response headers

`content-type: application/json` \
The return is a serialized JSON object with status information.

## Response status

`200`   **OK** \
Successful request. The dataset already exists on the Pbench Server; that is,
the MD5 hash is an exact match.

`201`   **CREATED** \
The tarball was successfully uploaded and the dataset has been created.

`400`   **BAD_REQUEST** \
One of the required headers is missing on incorrect, invalid query parameters
were specified, or a bad value was specified for a query parameter. The return
payload will be a JSON document with a `message` field containing details.

`401`   **UNAUTHORIZED** \
The client is not authenticated.

`503`   **SERVICE UNAVAILABLE** \
The server has been disabled using the `server-state` server configuration
setting in the [server configuration](./server_config.md) API. The response
body is an `application/json` document describing the current server state,
a message, and optional JSON data provided by the system administrator.

## Response body

The `application/json` response body consists of a JSON object giving a detailed
message on success or failure:

```json
{
    "message": "Dataset already exists",
    "errors": [ ]
}
```

or

```json
{
    "message": "at least one specified metadata key is invalid",
    "errors": [
        "Metadata key 'server.archiveonly' value 'abc' for dataset must be a boolean",
        "improper metadata syntax dataset.name=test must be 'k:v'",
        "Key test.foo is invalid or isn't settable",
    ],
}
```
