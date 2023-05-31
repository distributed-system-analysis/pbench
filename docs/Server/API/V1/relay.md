# `POST /api/v1/relay/<uri>`

This API creates a dataset resource by reading data from a Relay server. There
are two distinct steps involved:

1. A `GET` on the provided URI must return a "Relay manifest file". This is a
JSON file (`application/json` MIME format) providing the original tarball
filename, the tarball's MD5 hash value, a URI to read the tarball file, and
optionally metadata key/value pairs to be applied to the new dataset. (See
[Manifest file keys](#manifest-file-keys).)
2. A `GET` on the Relay manifest file's `uri` field value must return the
tarball file as an `application/octet-stream` payload, which will be stored by
the Pbench Server as a dataset.

## URI parameters

`<uri>` string \
The Relay server URI of the tarball's manifest `application/json` file. This
JSON object must provide a set of parameter keys as defined below in
[Manifest file keys](#manifest-file-keys).

## Manifest file keys

For example,

```json
{
    "uri": "https://relay.example.com/52adfdd3dbf2a87ed6c1c41a1ce278290064b0455f585149b3dadbe5a0b62f44",
    "md5": "22a4bc5748b920c6ce271eb68f08d91c",
    "name": "fio_rw_2018.02.01T22.40.57.tar.xz",
    "access": "private",
    "metadata": ["server.origin:myrelay", "global.agent:cloud1"]
}
```

`access`: [ `private` | `public` ] \
The desired initial access scope of the dataset. Select `public` to make the
dataset accessible to all clients, or `private` to make the dataset accessible
only to the owner. The default access scope if the key is omitted from the
manifest is `private`.

For example, `"access": "public"`

`md5`: tarball MD5 hash \
The MD5 hash of the compressed tarball file. This must match the actual tarball
octet stream specified by the manifest `uri` key.

`metadata`: [metadata key/value strings] \
A set of desired Pbench Server metadata key values to be assigned to the new
dataset. You can set the initial resource name (`dataset.name`), for example, as
well as assigning any keys in the `global` and `user` namespaces. See
[metadata](../metadata.md) for more information.

In particular the client can set any of:
* `dataset.name`: [default dataset name](../metadata.md#datasetname)
* `server.origin`: [dataset origin](../metadata.md#serverorigin)
* `server.archiveonly`: [suppress indexing](../metadata.md#serverarchiveonly)
* `server.deletion`: [default dataset expiration time](../metadata.md#serverdeletion).

`name`: The original tarball file name \
The string value must represent a legal filename with the compound type of
`.tar.xz` representing a `tar` archive compressed with the `xz` program.

`uri`: Relay URI resolving to the tarball file \
An HTTP `GET` on this URI, exactly as recorded, must return the original tarball
file as an `application/octet-stream`.

## Request headers

`authorization: bearer` token \
*Bearer* schema authorization assigns the ownership of the new dataset to the
authenticated user. E.g., `authorization: bearer <token>`

`content-length` tarball size \
The size of the request octet stream in bytes. Generally supplied automatically by
an upload agent such as Python `requests` or `curl`.

## Response headers

`content-type: application/json` \
The return is a serialized JSON object with status information.

## Response status

`200`   **OK** \
Successful request. The dataset MD5 hash is identical to that of a dataset
previously uploaded to the Pbench Server. This is assumed to be an identical
tarball, and the secondary URI (the `uri` field in the Relay manifest file)
has not been accessed.

`201`   **CREATED** \
The tarball was successfully uploaded and the dataset has been created.

`400`   **BAD_REQUEST** \
One of the required headers is missing or incorrect, invalid query parameters
were specified, or a bad value was specified for a query parameter. The return
payload will be a JSON document with a `message` field containing details.

`401`   **UNAUTHORIZED** \
The client is not authenticated.

`502`   **BAD GATEWAY** \
This means that a problem occurred reading either the manifest file or the
tarball from the Relay server. The return payload will be a JSON document with
a `message` field containing more information.

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
