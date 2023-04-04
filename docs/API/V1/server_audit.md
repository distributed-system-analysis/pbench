# `GET /api/v1/server/audit`

This API returns the Pbench Server audit log as an `application/json` document.
Various query parameters are available to filter the returned records.

## Query parameters

### `end`
The latest date to return.

### `start`
The earliest date to return.

### `dataset`
This is an alias for specifying [#object_id] and [#object_type] to select all
audit records for a specific dataset.

### `name`
Each type of Pbench Server "actor" has a simple name, so it's easy to select
all upload or index operations.
* `config`: Server configuration values were modified.
* `metadata`: Dataset metadata values were modified.
* `upload`: A dataset was uploaded to the server.

### `object_id`
Select by the object ID. For datasets, this is the `resource_id`; for users it's
the OIDC ID, and for server configuration settings there is no ID. This allows
selecting datasets (or users) that no longer exist, using the original values.

### `object_name`
Select by the name of an object at the time the audit record was generated. If
an object is deleted, or the object name is changed, older audit records retain
the previous name and can be used to track "phases in the object's evolution".
To track a dataset across name changes, use `object_id` and `object_type`, or
`dataset`.

### `object_type`
Select by the object type.
* `DATASET`: Dataset objects.
* `CONFIG`: Server config settings.
* `TEMPLATE`: Elasticsearch templates.
* `NONE`: Unspecified.
* `TOKEN`: API Key tokens.

### `operation`
The CRUD operation type associated with the audit records.

* `CREATE`: A resource was created.
* `READ`: A resource was read. (The Pbench Server does not generally audit read operations.)
* `UPDATE`: A resource was updated.
* `DELETE`: A resource was deleted.

### `reason`
Failure reason codes: additional information will be encoded in the `attributes`
JSON object, but can't be filtered directly.

* `PERMISSION`: The operation failed due to a permission failure.
* `INTERNAL`: The operation failed due to internal Pbench Server processing errors.
* `CONSISTENCY`: The operation failed due to resource or process consistency issues.

### `status`
Each linked set of audit records begins with a `BEGIN` record; the status of the
finalization record reflects the completion status.

* `BEGIN`: Begin an operation.
* `SUCCESS`: Successful completion of an operation.
* `FAILURE`: Total failure of an operation.
* `WARNING`: Partial failure of an operation.

### `user_id`
The OIDC ID of the user responsible for the operation.

### `user_name`
The username of the user responsible for the operation, or `BACKGROUND` when there's
no active user.

## Request headers

`authorization: bearer` token \
*Bearer* schema authorization for a user holding the `ADMIN` role is required
to access audit log data.

E.g., `authorization: bearer <token>`

## Response headers

`content-type: application/json` \
The return is a serialized JSON object with the selected audit log records.

## Response status

`200`   **OK** \
Successful request.

`401`   **UNAUTHORIZED** \
The client is not authenticated.

`403`   **FORBIDDEN** \
The authenticated client does not hold the `ADMIN` role required to access the
audit log.

`503`   **SERVICE UNAVAILABLE** \
The server has been disabled using the `server-state` server configuration
setting in the [server configuration](./server_config.md) API. The response
body is an `application/json` document describing the current server state,
a message, and optional JSON data provided by the system administrator.

## Response body

The `application/json` response body is a JSON document containing the selected
audit records.

### Examples

The `root_id` links multiple audit records from the `id` of the `BEGIN` operation
record.

The `attributes` JSON provides any additional information on the operation,
including at least a `message` field on failure.

The absolute UTC `timestamp` when the audit record was generated.

```python
GET /api/v1/server/audit?start=2023-03-26&name=upload&status=success

[
    {
        "attributes": {
            "access": "public",
            "metadata": {
                "global.server.legacy.hostname": "n010.intlab.redhat.com",
                "global.server.legacy.sha1": "9a54d5281",
                "global.server.legacy.version": "0.69.11"
            }
        },
        "id": 24156,
        "name": "upload",
        "object_id": "15a047579afab000606769e35e6aa478",
        "object_name": "fio__2023.03.26T00.14.30",
        "object_type": "DATASET",
        "operation": "CREATE",
        "reason": null,
        "root_id": 24155,
        "status": "SUCCESS",
        "timestamp": "2023-03-26T00:29:13.640724+00:00",
        "user_id": "3",
        "user_name": "legacy"
    },
    {
        "attributes": {
            "access": "public",
            "metadata": {
                "global.server.legacy.hostname": "n010.intlab.redhat.com",
                "global.server.legacy.sha1": "9a54d5281",
                "global.server.legacy.version": "0.69.11"
            }
        },
        "id": 24192,
        "name": "upload",
        "object_id": "f71a5a714e64649df9de0e5d68d52af9",
        "object_name": "uperf__2023.03.26T00.28.47",
        "object_type": "DATASET",
        "operation": "CREATE",
        "reason": null,
        "root_id": 24191,
        "status": "SUCCESS",
        "timestamp": "2023-03-26T00:33:12.407221+00:00",
        "user_id": "3",
        "user_name": "legacy"
    },
    {
        "attributes": {
            "access": "public",
            "metadata": {
                "global.server.legacy.hostname": "n010.intlab.redhat.com",
                "global.server.legacy.sha1": "9a54d5281",
                "global.server.legacy.version": "0.69.11"
            }
        },
        "id": 24236,
        "name": "upload",
        "object_id": "d1993694695a5eb3cb9f34902f0e31ce",
        "object_name": "uperf__2023.03.26T00.36.50",
        "object_type": "DATASET",
        "operation": "CREATE",
        "reason": null,
        "root_id": 24235,
        "status": "SUCCESS",
        "timestamp": "2023-03-26T00:41:12.851840+00:00",
        "user_id": "3",
        "user_name": "legacy"
    },
    {
        "attributes": {
            "access": "public",
            "metadata": {
                "global.server.legacy.hostname": "n010.intlab.redhat.com",
                "global.server.legacy.sha1": "9a54d5281",
                "global.server.legacy.version": "0.69.11"
            }
        },
        "id": 24450,
        "name": "upload",
        "object_id": "d69af9c9d827f2cd553f5ee535be4649",
        "object_name": "fio__2023.03.26T00.44.42",
        "object_type": "DATASET",
        "operation": "CREATE",
        "reason": null,
        "root_id": 24449,
        "status": "SUCCESS",
        "timestamp": "2023-03-26T02:14:14.539689+00:00",
        "user_id": "3",
        "user_name": "legacy"
    },
    {
        "attributes": {
            "access": "public",
            "metadata": {
                "global.server.legacy.hostname": "n010.intlab.redhat.com",
                "global.server.legacy.sha1": "9a54d5281",
                "global.server.legacy.version": "0.69.11"
            }
        },
        "id": 24534,
        "name": "upload",
        "object_id": "141b8c75d66a0e0d1e13eb9a7face6b9",
        "object_name": "uperf__2023.03.26T02.26.33",
        "object_type": "DATASET",
        "operation": "CREATE",
        "reason": null,
        "root_id": 24533,
        "status": "SUCCESS",
        "timestamp": "2023-03-26T02:42:13.794463+00:00",
        "user_id": "3",
        "user_name": "legacy"
    },
]
```
