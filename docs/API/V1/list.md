# `GET /api/v1/datasets/list`

This API returns an `application/json` document describing the set of datasets accessible to the client. (An unauthenticated client can only access "public" datasets.)

The list of datasets may be further filtered by "owner", "access", "name" substring, or by creation date range using the query parameters.

## Query parameters

`access`    string \
Select whether only `private` or only `public` access datasets will be included in the list. By default, all datasets readable by the authenticated user are included. For example, without constraints `/datasets/list` for an authenticated user will include all `public` datasets plus all datasets owned by the authenticated user; specifying `private` will show only the authenticated user's private datasets, while specifying `public` will show only `public` datasets (regardless of ownership).

`end` date/time \
Select only datasets created on or before the specified time.

`limit` integer \
"Paginate" the selected datasets by returning only `limit` datasets. This can be used in conjunction with `offset` to progress through the full list in smaller chunks either to assist with a paginated display or to limit data transfer requirements.

`metadata` list \
Request the named [metadata](../metadata.md) to be returned along with the resource name and ID. This can be a single metadata key path or comma-separated list of such strings. The `metadata` query parameter can be repeated. For example, `?metadata=dataset.created,server.deletion,user`, `?metadata=dataset.created&metadata=dataset.deletion,user` and `?metadata=dataset.created&metadata=dataset.deletion&metadata=user` are all equivalent.

`offset` integer \
"Paginate" the selected datasets by skipping the first datasets up to `offset`. This can be used in conjunction with `limit` to progress through the full list in smaller chunks either to assist with a paginated display or to limit data transfer requirements.

`owner` string \
The `username` property of a registered user. Only datasets owned by that user will be included in the list.

`start` date/time \
Select only datasets created on or after the specified time.

## Request headers

`authorization: bearer` token [_optional_] \
*Bearer* schema authorization is required to access any non-public dataset. E.g., `authorization: Bearer <token>`. If omitted, the client is unauthenticated and only `public` access datasets will be selected.

## Response headers

`content-type: application/json` \
The return is a serialized JSON object with information about the selected datasets.

## Response status

`401`   **UNAUTHORIZED** \
The client did not provide an authentication token and there is no public dataset with the name `<dataset>`.

`403`   **FORBIDDEN** \
The named `<dataset>` is not public and the authenticated user lacks authorization to read it.

`404`   **NOT FOUND** \
Either the `<dataset>` or the relative `<path>` within the dataset does not exist

## Response body

This returns an `application/json` response body describing the target of `<path>`, in terms of "file" and "directory" JSON objects.

When the target is a directory, the response object contains a list of subdirectories and a list of files; if the target is a file (either a regular file or a symlink) it returns the file object for that path.

When the target directory contains symlinks, the symlinks will be reported either in the `"file"` list (if the target of the symlink is a file) or in the `"directory"` list (if the target of the symlink is a directory).

### Directory

When the `<path>` refers to a directory within the dataset representation, Pbench returns a JSON object with a list of subdirectory objects and a list of file objects.

#### Directory object

The directory object gives the name of the directory, and a URI that can be used with a subsequent `GET` operation to get directory data about that nested path.

#### File object

The file object gives the name of the file and a URI that can be used with a subsequent `GET` operation to return the buffered byte stream of that file.

Note that soft links within the dataset representation will result in a URI returning a linked file's byte stream or a linked directory's [directory object](Directory object).

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

When the specified path is a leaf file (regular file or symlink), the response body is an `application/json` formatted "file object" as described above, including the name and filesystem metadata. The URI is provided which can be used to `GET` the file bytestream. (Assuming the file is a regular file or a symlink to a regular file.)

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