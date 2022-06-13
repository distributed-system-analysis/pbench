# `GET /api/v1/datasets/contents/<dataset><path>`

This API returns an `application/json` document describing a `<path>` within the `<dataset>` tarball representation.

## URI parameters

`<dataset>` string \
The resource ID of a Pbench dataset on the server.

`<path>`    string \
The path of an item in the dataset inventory, as captured by the Pbench agent packaging; for example, `/` for the root, or `/1-default/` for the default first iteration directory.

## Request headers

`authorization: bearer` token \
*Bearer* schema authorization is required to access any non-public dataset. E.g., `authorization: Bearer <token>`

## Response headers

`content-type: application/json` \
The return is a serialized JSON object with information about the named file.

## Response status

`401`   **UNAUTHORIZED** \
The client did not provide an authentication token and there is no public dataset with the resource ID `<dataset>`.

`403`   **FORBIDDEN** \
The named `<dataset>` is not public and the authenticated user lacks authorization to read it.

`404`   **NOT FOUND** \
Either the `<dataset>` or the relative `<path>` within the dataset does not exist

## Response body

This API returns an `application/json` response body consisting of a JSON object which describes the target `<path>`, in terms of lists of "file" and "directory" JSON objects (as described below).

When the target is a directory, the response object contains a list of subdirectories and a list of files; if the target is a file it returns the file object for that path.

### Directory

When the `<path>` refers to a directory within the dataset representation, Pbench returns a JSON object containing a list of subdirectory objects (`directories`) and a list of file objects (`files`).

#### Directory object

The directory object gives the name of the directory, and a URI that can be used with a subsequent `GET` operation to get directory data for that nested path.

#### File object

The file object gives the name of the file and a URI that can be used with a subsequent `GET` operation to return the raw byte stream of that file.

Note that symlinks within the dataset representation will result in a URI returning the linked file's byte stream or the linked directory's [directory object](#directory-object).

#### Example

```json
{
    "directories": [
        {
            "name": "1-iter1",
            "uri": "http://hostname/api/v1/datasets/contents/<id><path>/1-iter1"
        },
        {
            "sysinfo",
            "uri": "http://hostname/api/v1/datasets/contents/<id><path>/sysinfo"
        }
        [...]
    ],
    "files": [
        {
        "name": ".iterations",
        "mtime": "2022-05-18T16:02:30",
        "size": 24,
        "mode": "0o644",
        "type": "reg",
        "uri": "http://hostname/api/v1/datasets/inventory/<id><path>/.iterations"
        },
        {
        "name": "iteration.lis",
        "mtime": "2022-05-18T16:02:06",
        "size": 18,
        "mode": "0o644",
        "type": "reg",
        "uri": "http://hostname/api/v1/datasets/inventory/<id><path>/iteration.lis"
        },
        [...]
    ]
}
```

### File

When the specified path is a leaf file (regular file or symlink), the response body is an `application/json` formatted [file object](#file-object), including the name and filesystem metadata. A URI is provided which can be used to `GET` the file's contents as a raw byte stream.

#### Example

```json
{
    "name": "iteration.lis",
    "mtime": "2022-05-18T16:02:06",
    "size": 18,
    "mode": "0o644",
    "type": "reg",
    "uri": "http://hostname/api/v1/datasets/inventory/<id>><path>"
}
```