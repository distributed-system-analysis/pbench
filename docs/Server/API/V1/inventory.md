# `GET /api/v1/datasets/<dataset>/inventory/[<path>]`

This API returns an `application/octet-stream` document containing the raw byte
stream of a regular file at the `<path>` within the `<dataset>` tarball
representation.

## URI parameters

`<dataset>` string \
The resource ID of a Pbench dataset on the server.

`<path>`    string \
The resource path of an item in the dataset inventory, as captured by the
Pbench Agent packaging; for example, `/metadata.log` for a file named
`metadata.log` at the top level of the dataset tarball, or `/dir1/dir2/file.txt`
for a `file.txt` file in a directory named `dir2` within a directory called
`dir1` at the top level of the dataset tarball.

## Request headers

`authorization: bearer` token \
*Bearer* schema authorization is required to access any non-public dataset.
E.g., `authorization: bearer <token>`

## Response headers

`content-type: application/octet-stream` \
The return is a raw byte stream representing the contents of the named file.

`content-disposition: <action>; filename=<name>` \
This header defines the recommended client action on receiving the byte stream.
The `<action>` types are either `inline` which suggests that the data can be
displayed "inline" by a web browser or `attachment` which suggests that the data
should be saved into a new file. The `<name>` is the original filename on the
Pbench Server. For example,

```
content-disposition: attachment; filename=pbench-fio-config-2023-06-29-00:14:50.tar.xz
```

or

```
content-disposition: inline; filename=data.txt
```

## Resource access

* Requires `READ` access to the `<dataset>` resource

See [Access model](../access_model.md)

## Response status

`200`   **OK** \
Successful request.

`401`   **UNAUTHORIZED** \
The client is not authenticated.

`403`   **FORBIDDEN** \
The authenticated client does not have READ access to the specified dataset.

`404`   **NOT FOUND** \
Either the `<dataset>` or the relative `<path>` within the dataset does not
exist.

`415` **UNSUPPORTED MEDIA TYPE** \
The `<path>` refers to a directory. Use
`/api/v1/dataset/<dataset>/contents/<path>` to request a JSON response document
describing the directory contents.

`503`   **SERVICE UNAVAILABLE** \
The server has been disabled using the `server-state` server configuration
setting in the [server configuration](./server_config.md) API. The response
body is an `application/json` document describing the current server state,
a message, and optional JSON data provided by the system administrator.

## Response body

The `application/octet-stream` response body is the raw byte stream contents of
the specified file.
