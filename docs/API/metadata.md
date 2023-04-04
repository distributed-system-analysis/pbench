## Dataset metadata

A dataset is referenced by a formal resource ID, and also has a resource name
for convenience. The Pbench Server also maintains metadata about each dataset,
which can help with searching and analysis. Some metadata is modifyable by an
authenticated user, while other metadata is maintained internally by the server
and can't be changed. Authenticated users can also add any additional metadata
that might be of use.

Dataset metadata is represented as a set of nested JSON objects. There are four
distinct key namespaces. These can be addressed (read or changed) at any level
of the hierarchy using a dotted name path, for example `dataset.resource_id`
for a dataset's resource ID, or `global.environment.cluster.ip`. The keys are
lowercase alphabetic, plus digits, hyphen, and underscore: so `global.u-7` is
OK, but `global.Frank` isn't.

The four namespaces are:
* `dataset` provides inherent attributes of the dataset, including the full
`metadata.log` as `dataset.metalog`. Most of these attributes cannot be changed
after creation.
* `server` provides server management state about a dataset. Most of these
cannot be changed by the user. While many may not be directly meaningful to the
user, the Pbench Server does not hide them. (Beware that retrieving the entire
`server` namespace may result in a substantial amount of data that's of little
use to a client.)
* `global` provides user-controlled dataset metadata which can only be modified
by the owner of the dataset, but is visible to anyone with read access to the
dataset. By convention, a client should use a unique second-level key to avoid
conflicting paths. For example, the Pbench Dashboard uses `global.dashboard`.
* `user` provides a metadata namespace for each dataset that's private to the
authenticated user: each user will see their own set of nested object structure
and values, and these are not shareable. Even if you don't own a dataset you
can set your own private `user` metadata to help you categorize that dataset
and to find it again. By convention, a client should use a unique second-level
key to avoid conflicting paths. For example, the Pbench Dashboard uses
`user.dashboard`.

When a dataset is first processed, the Pbench Server will populate basic
metadata, including the creation timestamp, the owner of the dataset (the
username associated with the token given to the Pbench Agent
`pbench-results-move` command), and the full contents of the dataset's
`metadata.log` file inside the dataset tarball. These are all accessible
under the `dataset` metadata key namespace.

The Pbench Server will also calculate a default deletion date for the dataset
based on the owner's retention policy and the server administrator's retention
policy along with some other internal management context. The expected deletion
date is accessible under the `server` metadata key namespace as
`server.deletion`

Clients can also set arbitrary metadata through the `global` and `user`
metadata namespaces.

For example, given the following hypothetical `user` JSON value:

```json
{
    "project": ["OCP", "customer"],
    "tracker": {"examined": "2022-05-15", "revisit": true},
    "analysis": {"cpu": "high", "memory": "nominal"}
}
```

requesting the metadata `user` (e.g., with `/api/v1/datasets/list?metadata=user`)
would return the entire JSON value. In addition:
* `user.project` would return `["OCP", "customer"]`
* `user.tracker.examined` would return `"2022-05-15"`
* `user.analysis` would return `{"cpu": "high", "memory": "nominal"}`

## Metadata namespaces

There are currently four metadata namespaces.

* The `dataset` and `server` namespaces are defined and managed by Pbench.
* The `global` namespace allows an authenticated client to define an
arbitrary nested set of JSON objects associated with a specific dataset
owned by the authenticated user.
* The `user` namespace is similar to `global` in structure. The difference
is that where metadata in the `global` namespace can only be modified by the
owner of the dataset and is visible to all clients with read access to the
dataset, any authenticated user can set arbitrary values in the `user`
namespace and those values are visible only to the user who set them. Other
users may set different values for the same `user` namespace keys on the
dataset or may use completely different keys.

All of these namespaces are tied to a particular dataset resource ID, and cease
to exist if the associated dataset is deleted.

### Dataset namespace

This defines the dataset resource, and contains metadata received from the
Pbench Agent, including the full contents of a `metadata.log` file created
while gathering results and during dataset packaging.

This namespace includes the resource name, which can be modified by the owner
of the dataset by setting the metadata key `dataset.name`. All other key values
in this namespace are controlled by the server and cannot be changed by the
client.

The `metadata.log` data is represented under the key `dataset.metalog` and can
be queried as part of the entire dataset using the `dataset` key, as a discrete
sub-document using `dataset.metalog` in specific "sections" such as
`dataset.metalog.pbench` or targeting a specific value like
`dataset.metalog.pbench.script`.

### Server namespace

This defines internal Pbench Server management state related to a dataset
that's not inherent to the representation of the user's performance metrics.
These are generally not useful to clients, and some can be large. There are
three values in this namespace that clients can modify:

* `server.deletion` is a date after which the Pbench Server may choose to
delete the dataset. This is computed when a dataset is received based on user
profile preferences and server configuration; but it can be modified by the
owner of the dataset, as long as the new timestamp remains within the maximum
allowed server data retention period.
* `server.archiveonly` is a boolean that can be set to a boolean True when a
dataset is first uploaded to prevent the Pbench Server from unpacking or
indexing the dataset. That is, the server will archive the dataset and it can
be retrieved for offline analysis but the server will do nothing else with it.
The value can be specified as "t", "true", "y" or "yes" (case insensitive) for
True, and "f", "false", "n", or "no" (also case insensitive) for False. Note
that this is currently only interpreted by the Pbench Server when a dataset is
first uploaded, and will inhibit unpacking and indexing the dataset. It can be
changed later, but the server currently takes no action on such changes.
* `server.origin` is a way to record the origin of a dataset. This is a string
value, and the Pbench Server does not interpret it.

### Global namespace

The server will never modify or directly interpret values in this namespace. An
authenticated client representing the owner of a dataset can set any keys
within this namespace to any valid JSON values (string, number, boolean, list,
or nested objects) for retrieval later. All clients with read access to the
dataset will see the same values.

The recommended best practice is to select a project sub-key that will be unique
and minimize the risk of collisions between various clients. The Pbench Dashboard
project, for example, will store all client metadata under the `global.dashboard`
sub-namespace, for example `global.dashboard.seen`. A hypothetical client named
"clienta" might use `global.clienta`, for example `global.clienta.configuration`.

Pbench Server clients can use metadata to filter selected datasets in the
collection browser, [datasets](V1/list.md).

### User namespace

The server will never modify or directly interpret values in this namespace. An
authenticated client able to see a dataset can set metadata keys within this
namespace to any valid JSON values (string, number, boolean, list, or nested
objects) for retrieval later. Each authenticated client may set distinct values
for the same keys, or use completely different keys, and can retrieve those
values later. A client authenticated for another user has its own completely
unique `user` namespace.

The `user` metadata namespace behaves as a user-specific sub-resource under the
dataset. Any authenticated client has UPDATE and DELETE access to this private
sub-resource as long as the client has READ access to the dataset. See
[Access model](./access_model.md) for general information about the Pbench
Server access controls.

The recommended best practice is to select a project sub-key that will be unique
to minimize the risk of collisions between various clients. The Pbench Dashboard
project, for example, will store all user-specific client metadata under the
`user.dashboard` sub-namespace, for example `user.dashboard.favorite`. A
hypothetical client named "clienta" might use `user.clienta`, for example
`user.clienta.configuration`.

An unauthenticated client can neither set nor retrieve any `user` namespace
values; such a client will always see the `user` namespace as empty.
