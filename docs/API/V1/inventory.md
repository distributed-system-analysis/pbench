# `GET /api/v1/datasets/inventory/<dataset><path>`

This API returns an `application/octet-stream` document containing the raw byte stream of a regular file (or soft link to a regular file) at the relative `<path>` within the `<dataset>` tarball representation.

## URI parameters

`<dataset>` string
The resource ID of a Pbench dataset on the server.

`<path>`    string
The relative resource path of an item in the dataset inventory, as captured by the Pbench agent packaging; for example, `/metadata.log` for the dataset metadata, or `/1-default/sample1/result.txt` for the default first iteration results.

## Request headers

`authorization: bearer` token \
*Bearer* schema authorization is required to access any non-public dataset. E.g., `authorization: Bearer <token>`

## Response headers

`content-type: application/octet-stream` \
The return is a raw byte stream representing the contents of the named file.

## Response status

`401`   **UNAUTHORIZED** \
The client did not provide an authentication token and there is no public dataset with the name `<dataset>`.

`403`   **FORBIDDEN** \
The named `<dataset>` is not public and the authenticated user lacks authorization to read it.

`404`   **NOT FOUND** \
Either the `<dataset>` or the relative `<path>` within the dataset does not exist

`415` **UNSUPPORTED MEDIA TYPE** \
The `<path>` refers to a directory. Use `/api/v1/dataset/contents/<dataset><path>` to acquire a JSON response document describing the directory contents.

## Response body

The raw byte stream of the regular file will be returned.