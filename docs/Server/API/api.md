# Pbench Server API documentation

The Pbench Server API provides the interface to Pbench data for use by the UI
dashboard as well as any other web clients.

The Pbench Server provides a set of HTTP endpoints to manage user
authentication and curated performance information, called "dataset resources"
or just "datasets". A dataset represents the aggregation of server artifacts
associated with the results of a performance experiment, for example the
benchmarked workload and tool data collected from `pbench-fio` or from
`pbench-user-benchmark`.

The [V1 API](V1/README.md) provides a RESTful functional interface oriented
around the "dataset" resource.

The Pbench Server APIs accept parameters from a variety of sources. See the
individual API documentation for details.
1. Some parameters, especially "resource ids", are embedded in the URI, such as
`/api/v1/datasets/<resource_id>`;
2. Some parameters are passed as query parameters, such as
`/api/v1/datasets?name:fio`;
3. For `PUT` and `POST` APIs, some parameters may be passed as a JSON
(`application/json` content type) request payload, such as
`{"metadata": {"dataset.name": "new name"}}` or as an `application/octet-stream`
byte stream, such as uploading a new results tarball file.
