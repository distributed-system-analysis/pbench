# `GET /api/v1/datasets/contents/<dataset>/<path>`

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
`/api/v1/datasets/contents/<dataset>/` represents the root, and
`/api/v1/datasets/contents/<dataset>/directory/` represents a directory named
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

`401`   **UNAUTHORIZED** \
The client is not authenticated and does not have READ access to the specified
dataset.

`403`   **FORBIDDEN** \
The authenticated client does not have READ access to the specified dataset.

`404`   **NOT FOUND** \
Either the `<dataset>` or the relative `<path>` within the dataset does not
exist.

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
            "name": "1-iter1",
            "type": "dir",
            "uri": "http://hostname/api/v1/datasets/contents/<id>/1-iter1"
        },
        {
            "sysinfo",
            "type": "dir",
            "uri": "http://hostname/api/v1/datasets/contents/<id>/sysinfo"
        },
        ...
    ],
    "files": [
        {
        "name": ".iterations",
        "mtime": "2022-05-18T16:02:30",
        "size": 24,
        "mode": "0o644",
        "type": "reg",
        "uri": "http://hostname/api/v1/datasets/inventory/<id>/.iterations"
        },
        {
        "name": "iteration.lis",
        "mtime": "2022-05-18T16:02:06",
        "size": 18,
        "mode": "0o644",
        "type": "reg",
        "uri": "http://hostname/api/v1/datasets/inventory/<id>/iteration.lis"
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
    "uri": "http://hostname/api/v1/datasets/contents/<id>/sample1"
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
    "uri": "http://hostname/api/v1/datasets/inventory/<id>/<path>"
}
```
