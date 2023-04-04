# `PUT /api/v1/upload/<file>`

This API creates a dataset resource by uploading a tarball to the Pbench Server.
The tarball must be compressed with the `xz` program, and have the compound
file type suffix of ".tar.xz".

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
A set of desired Pbench Server metadata keys to be assigned to the new dataset.
You can set the initial resource name (`dataset.name`), for example, as well as
assigning any keys in the `global` and `user` namespaces.

In particular the `server.archiveonly` metadata key can be set to `false` to
prevent the Pbench Server from unpacking or indexing the tarball, for example
when the tarball doesn't contain the expected Pbench Agent `metadata.log`.
The tarball will be archived on the server, is visible in the dataset
collection and can be decorated with metadata, but won't be indexed.

For example, `?metadata=server.archiveonly:true,global.project:oidc`

## Request headers

`authorization: bearer` token \
*Bearer* schema authorization assigns the ownership of the new dataset to the
authenticated user. E.g., `authorization: bearer <token>`

`content-length` tarball size \
The size of the request octet stream in bytes. Generally supplied automatically by
an upload agent such as Python `requests` or `curl`.

`content-md5` MD5 hash \
The MD5 hash of the compressed tarball file. This must match the actual tarball
octet stream provided as the request body.

## Response headers

`content-type: application/json` \
The return is a serialized JSON object with status information.

## Response status

`200`   **OK** \
Successful request. The dataset MD5 hash is identical to that of a dataset
previously uploaded to the Pbench Server. This is assumed to be an identical
tarball.

`201`   **CREATED** \
The tarball was successfully uploaded and the dataset has been created.

`400`   **BAD_REQUEST** \
One of the required headers is missing or incorrect, invalid query parameters
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
