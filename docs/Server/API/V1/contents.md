# `GET /api/v1/datasets/<dataset>/contents/[<path>]`

This API returns an `application/json` document describing a file or the
content of a directory at a specified `<path>` within the `<dataset>` tarball
representation.

## URI parameters

`<dataset>` string \
The resource ID of a dataset on the Pbench Server.

`<path>`    string \
The path of an item in the dataset inventory, as captured by the Pbench Agent
packaging. Note that the `/` separating the two parameters serves to mark the
relative root directory of the tarball. For example
`/api/v1/datasets/<dataset>/contents/` represents the root, and
`/api/v1/datasets/<dataset>/contents/directory/` represents a directory named
`directory` at the root level.

## Request headers

`authorization: bearer` token \
*Bearer* schema authorization is required to access any non-public dataset.
E.g., `authorization: bearer <token>`

## Response headers

`content-type: application/json` \
The return is a serialized JSON object with information about the named file.

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

`503`   **SERVICE UNAVAILABLE** \
The server has been disabled using the `server-state` server configuration
setting in the [server configuration](./server_config.md) API. The response
body is an `application/json` document describing the current server state,
a message, and optional JSON data provided by the system administrator.

## Response body

The `application/json` response body consists of a JSON object describing the
file or directory at a target `<path>` within a dataset tarball.

When the `<path>` refers to a directory, the response object is described in
[Directory object](#directory-object); when the `<path>` refers to a file, the
response object is described in [File object](#file-object).

### Directory object

When the `<path>` refers to a directory within the dataset representation,
Pbench returns a JSON object with two list fields:
* `"directories"` is a list of [subdirectory objects](#subdirectory-object), and
* `"files"` is a list of [file objects](#file-object)

```json
{
    "directories": [
        {
            "name": "dir1",
            "type": "dir",
            "uri": "https://hostname/api/v1/datasets/<id>/contents/dir1"
        },
        {
            "name": "dir2",
            "type": "dir",
            "uri": "https://hostname/api/v1/datasets/<id>/contents/dir2"
        },
        ...
    ],
    "files": [
        {
        "name": "file.txt",
        "mtime": "2022-05-18T16:02:30",
        "size": 24,
        "mode": "0o644",
        "type": "reg",
        "uri": "https://hostname/api/v1/datasets/<id>/inventory/file.txt"
        },
        {
        "name": "data.lis",
        "mtime": "2022-05-18T16:02:06",
        "size": 18,
        "mode": "0o644",
        "type": "reg",
        "uri": "https://hostname/api/v1/datasets/<id>/inventory/data.lis"
        },
        ...
    ]
}
```

#### Subdirectory object

The subdirectory object gives the name of the directory, the type of the entry,
and a URI that can be used with a subsequent `GET` operation to return a
[directory object](#directory-object) for that nested path.

When a directory contains a symlink to a directory, that subdirectory name will
appear in the `"directories"` list, but will be designated with a `type` of
`sym` instead of `dir`.

The `type` codes are:
* `dir`: Directory
* `sym`: Symbolic link

```json
{
    "name": "reference-result",
    "type": "sym",
    "uri": "https://hostname/api/v1/datasets/<id>/contents/linkresult"
},
{
    "name": "directory",
    "type": "dir",
    "uri": "https://hostname/api/v1/datasets/<id>/contents/directory"
}
```

### File object

The file object gives the name of the file, file system information about that
file, and a URI that can be used with a subsequent `GET` operation to return
the raw byte stream of that file.

The file system information includes:
* `mtime`: the file's last modification time,
* `size`: the size of the file,
* `mode`: the file permissions (as an octal "mode" string), and
* `type`: the file's type. The type values are:
  * `reg`: Regular UNIX file
  * `sym`: Symbolic link

Note that symlinks to files within the dataset representation will result in a
URI returning the linked file's byte stream.

```json
{
    "name": "iteration.lis",
    "mtime": "2022-05-18T16:02:06",
    "size": 18,
    "mode": "0o644",
    "type": "reg",
    "uri": "https://hostname/api/v1/datasets/<id>/inventory/<path>"
}
```
