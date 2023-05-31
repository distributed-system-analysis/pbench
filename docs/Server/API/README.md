# Pbench Server API documentation

The Pbench Server API provides the interface to Pbench data for use by the UI
dashboard as well as any other web clients.

The Pbench Server provides a set of HTTP endpoints to manage user
authentication and curated performance information, called "dataset resources"
or just "datasets".

The [V1 API](V1/README.md) provides a REST-like functional interface.

The Pbench Server APIs accept parameters from a variety of sources. See the
individual API documentation for details.
1. Some parameters, especially "resource ids", are embedded in the URI, such as
`/api/v1/datasets/<resource_id>`;
2. Some parameters are passed as query parameters, such as
`/api/v1/datasets?name:fio`;
3. For `PUT` and `POST` APIs, parameters may also be passed as a JSON
(`application/json` content type) request payload, such as
`{"metadata": {"dataset.name": "new name"}}`
