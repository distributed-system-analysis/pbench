# Pbench Server API documentation

The Pbench Server API provides the interface to Pbench data for use by the UI
dashboard as well as any other web clients.

The Pbench Server provides a set of HTTP endpoints to manage user
authentication and curated performance information, called "dataset resources"
or just "datasets".

The [V1 API](V1/README.md) provides a functional interface that's not quite
standard REST. The intent is to migrate to a cleaner resource-oriented REST
style for a future V2 API.

The Pbench Server primarily uses serialized JSON parameters (mimetype
`application/json`) both for request bodies and response bodies. A few
exceptions use raw byte streams (`application/octet-stream`) to allow uploading
new datasets and to access individual files from a dataset.
