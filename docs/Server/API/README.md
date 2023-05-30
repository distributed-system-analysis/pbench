# Pbench Server API documentation

The Pbench Server API provides the interface to Pbench data for use by the UI
dashboard as well as any other web clients.

The Pbench Server provides a set of HTTP endpoints to manage user
authentication and curated performance information, called "dataset resources"
or just "datasets".

The [V1 API](V1/README.md) provides a REST-like functional interface.

The Pbench Server APIs use a combination of parameters embedded in the URI path
along with query parameters and serialized JSON parameters (mimetype
`application/json`) for requests. A few exceptions use raw byte streams
(`application/octet-stream`) to allow uploading new datasets and to access
individual files from a dataset.
