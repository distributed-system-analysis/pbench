# `GET /api/v1/datasets/inventory/<dataset><path>`

This API returns an `application/octet-stream` document containing the raw byte
stream of a regular file at the `<path>` within the `<dataset>` tarball
representation.

## URI parameters

`<dataset>` string \
The resource ID of a Pbench dataset on the server.

`<path>`    string \
The resource path of an item in the dataset inventory, as captured by the
Pbench Agent packaging; for example, `/metadata.log` for the dataset metadata,
or `/1-default/sample1/result.txt` for the default first iteration results.

## Request headers

`authorization: bearer` token \
*Bearer* schema authorization is required to access any non-public dataset.
E.g., `authorization: bearer <token>`

## Response headers

`content-type: application/octet-stream` \
The return is a raw byte stream representing the contents of the named file.

## Resource access

* `READ` access to the `<dataset>` resource

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

`415` **UNSUPPORTED MEDIA TYPE** \
The `<path>` refers to a directory. Use
`/api/v1/dataset/contents/<dataset><path>` to request a JSON response document
describing the directory contents.

## Response body

The `application/octet-stream` response body is the raw byte stream contents of
the specified file.
