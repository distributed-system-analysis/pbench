# Pbench Server API documentation

The Pbench Server API provides a RESTful HTTPS interface to curated Pbench
performance data for use by the UI dashboard as well as any other web clients.

The performance results data associated with an experiment is collectively
referred to as a "dataset". The dataset resource is initially defined by the
".tar.xz" tar ball uploaded to the Pbench Server. The server extracts and
creates metadata describing the dataset, and (if appropriate) indexes synthetic
benchmark data in Elasticsearch to support later analysis.

The [V1 API](V1/README.md) provides access to the original tar ball, the
original performance results file structure within the tarball, Pbench Server
[metadata](metadata.md), and the Elasticsearch indexed data.

The Pbench Server APIs accept parameters from a variety of sources. See the
individual API documentation for details.
1. Some parameters, especially "resource ids", are embedded in the URI, such as
`/api/v1/datasets/<resource_id>`;
2. Some parameters are passed as query parameters, such as
`/api/v1/datasets?filter=server.benchmark:fio`;
3. For `PUT` and `POST` APIs, some parameters may be passed as a JSON
(`application/json` content type) request payload, such as
`{"metadata": {"dataset.name": "new name"}}` or as an `application/octet-stream`
byte stream, such as uploading a new results tarball file.
