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
assigning any keys in the `global` and `user` namespaces. See
[metadata](../metadata.md) for more information.

In particular the client can set any of:
* `dataset.name`: [default dataset name](../metadata.md#datasetname)
* `server.origin`: [dataset origin](../metadata.md#serverorigin)
* `server.archiveonly`: [suppress indexing](../metadata.md#serverarchiveonly)
* `server.deletion`: [default dataset expiration time](../metadata.md#serverdeletion).

For example, `?metadata=server.archiveonly:true,global.project:oidc`

__Typed metadata__

When you set metadata dynamically using `PUT /datasets/<id>/metadata`, you
specify a JSON object for each key, so defining typed metadata is implicit in
the JSON object interpretation.

When using the `?metadata` query parameter, you're limited to writing strings,
and it's not quite so straightfoward. The string can contain type information
to compensate for the limitation. Each `?metadata` string is a comma-separated
list of "metadata expressions" of the form "<key>:<value>[:<type>]". If the
":<type>" is omitted, type is assumed to be "str". For example, you can specify
integer metadata values using ":int" (`global.mine.count:1:int`).

Types:
* `str` (default) The value is a string. If you want to include "," or ":"
  characters, you can quote the value using matched (and potentially nested)
  single and double quote characters. For example `<key>:'2023-10-01:10:23':str`
  will set the specified key to the value `2023-10-01:10:23`.
* `bool` The value is a (JSON format) boolean, `true` or `false`. For example
  `<key>:true:bool` will set the specified key to the boolean value `true`.
* `int` The value is an integer. For example `<key>:1:int` will set the
  specified key to the integer value 1.
* `float` The value is a floating point number. For example `<key>:1.0:float`
  will set the specified key to the floating point value 1.0.
* `json` The value is a quoted serialized JSON object representation. For
  example, `<key>:'{"str": "string", "int": 1, "bool": true}':json` will set
  the specified key to the JSON object `{"str": "string", "int": 1, "bool": true}`

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

The `application/json` response body consists of a JSON object containing a
`message` field. On failure this will describe the nature of the problem and
in some cases an `errors` array will provide details for cases where multiple
problems can occur.

```json
{
    "message": "File successfully uploaded"
}
```

or

```json
{
    "message": "Dataset already exists",
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
