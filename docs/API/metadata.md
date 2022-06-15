## Dataset metadata

A dataset is referenced by a formal resource ID, and also has a resource name
for convenience. The Pbench server also maintains metadata about each dataset,
which can help with searching and analysis. Some metadata is modifyable by an
authenticated user, while other metadata is maintained internally by the server
and can't be changed. Authenticated users can also add any additional metadata
that might be of use.

>__NOTE__: right now the ability to search and filter using metadata is
limited, but our intent is to be able to use any defined metadata value both
for searches and to filter the results of [datasets/list](V1/list.md).

When a dataset is first processed, the Pbench Server will populate basic
metadata, including the creation timestamp, the owner of the dataset (the
username associated with the token given to the Pbench Agent
`pbench-results-move` command), and the full contents of the dataset's
`metadata.log` file inside the dataset tarball. These are all accessible
under the `dataset` metadata key namespace.

The Pbench server will also calculate a default deletion date for the dataset
based on the owner's retention policy and the server administrator's retention
policy along with some other internal management context. The expected deletion
date is accessible under the `server` metadata key namespace.

Clients can also set arbitrary metadata through the "dashboard" and "user"
metadata namespaces:
* The "dashboard" namespace can only be modified by the owner of the dataset,
and is visible to anyone with read access to the dataset.
* The "user" namespace is private to each authenticated user, and even if you
don't own a dataset you can set your own private "user" metadata to help you
categorize that dataset and to find it again.

Metadata namespaces are hierarchical, and are exposed as nested JSON objects.
You can address an entire namespace, e.g., `dashboard` or `dataset` and
retrieve the entire JSON object, or you can address nested objects or values
using a dotted metadata key path like `dashboard.contact.email` or
`dataset.metalog.pbench.script`.

For example, given the following hypothetical `user` JSON value:

```json
{
    "project": ["OCP", "customer"],
    "tracker": {"examined": "2022-05-15", "revisit": true},
    "analysis": {"cpu": "high", "memory": "nominal"}
}
```

requesting the metadata `user` (e.g., with `datasets/list?metadata=user`) would
return the entire JSON value. In addition:
* `project` would return `["OCP", "customer"]`
* `user.tracker.examined` would return `"2022-05-15"`
* `user.analysis` would return `{"cpu": "high", "memory": "nominal"}`

## Metadata namespaces

There are currently four metadata namespaces.

* The `dataset` and `server` namespaces are defined and managed by Pbench.
* The `dashboard` namespace allows an authenticated client to define an
arbitrary nested set of JSON objects associated with a specific dataset
owned by the authenticated user.
* The `user` namespace is similar; except that where metadata in the
`dashboard` namespace can only be modified by the owner of the dataset, and is
visible to all clients with read access to the dataset, any authenticated user
can set arbitrary values in the `user` namespace and those values are visible
only to the same authenticated user. Other users may set different values for
the same `user` namespace keys on the dataset, or completely different keys.

### Dataset namespace

This defines the dataset resource, and contains metadata recieved from the
Pbench Agent, including the full contents of a `metadata.log` file created
while gathering results and during dataset packaging.

This namespace includes the resource name, which can be modified by the owner
of the dataset. All other data in this namespace is controlled by the server
and cannot be changed by the client.

### Server namespace

This defines internal Pbench Server management state related to a dataset
that's not inherent to the representation of the user's performance metrics.
Most of this is not of much use to external clients, but can be observed.

The exception is `server.deletion`, which is a time after which the Pbench
Server may choose to delete the dataset. This is computed when a dataset is
received based on user profile preferances and server configuration; but it can
be modified by the owner of the dataset, as long as the new timestamp remains
within the maximum allowed server data retention period.

### Dashboard namespace

The server will never modify or directly interpret values in this namespace. An
authenticated client representing the owner of a dataset can set any keys
within this namespace to any valid JSON values (string, integer, boolean, list,
or nested objects) for retrieval later. All clients with read access to the
dataset will see the same values.

__NOTE__: The server will in the future be able to use these values to filter
the selected datasets for [datasets/list](V1/list.md).

### User namespace

This is treated almost exactly like the `dashboard` namespace, except that the
values stored here are specific to the authenticated user. Each authenticated
client may set distinct values for the same keys, and will be able to retrieve
those values later. A client authenticated for some other user will see a
completely different set of values. An unauthenticated client can neither set
nor retrieve any `user` namespace values; such a client will always see the
`user` namespace as empty.
