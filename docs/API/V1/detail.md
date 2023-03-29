# `GET /api/v1/datasets/<dataset>/detail`

This API returns detailed information about a dataset's run environment from the
Elasticsearch index. It can also return Pbench Server [metadata](../metadata.md).

Note that this information is mostly acquired from the dataset's `metadata.log`
file which is also directly accessible as metadata through `dataset.metalog`.
This API is "mostly obsolete".

## URI parameters

`<dataset>` string \
The resource ID of a Pbench dataset on the server.

## Query parameters

`metadata` requested metadata keys \
A list of server metadata tags; see [Metadata](../metadata.md). For example,
`?metadata=dataset.access,global.server.legacy` will return the value of the
two metadata keys `dataset.access` (the dataset's access scope) and
`global.server.legacy` (a user-defined global value).

## Request headers

`authorization: bearer` token \
*Bearer* schema authorization is required to access any non-public dataset.
E.g., `authorization: bearer <token>`

## Response headers

`content-type: application/json` \
The return is a JSON document containing the summary "run" data from the
dataset index.

## Resource access

* Requires `READ` access to the `<dataset>` resource

See [Access model](../access_model.md)

## Response status

`200`   **OK** \
Successful request.

`400`   **BAD_REQUEST** \
One or more metadata keys specified were unacceptable.

`401`   **UNAUTHORIZED** \
The client is not authenticated and does not have READ access to the specified
dataset.

`403`   **FORBIDDEN** \
The authenticated client does not have READ access to the specified dataset.

`404`   **NOT FOUND** \
The `<dataset>` does not exist.

`503`   **SERVICE UNAVAILABLE** \
The server has been disabled using the `server-state` server configuration
setting in the [server configuration](./server_config.md) API. The response
body is an `application/json` document describing the current server state,
a message, and optional JSON data provided by the system administrator.

## Response body

The `application/json` response body is a JSON object containing the dataset
index "run" data and any requested server metadata, as follows.

This assumes the query parameter `?metadata=dataset.access`.

```json
{
    "hostTools": [
        {
            "hostname": "controller.example.com",
            "tools": {
                "hostname-alias": "",
                "hostname-all-fqdns": "host.containers.internal controller.example.com controller.example.com controller.example.com",
                "hostname-all-ip-addresses": "10.1.36.93 172.21.63.246 10.1.63.92 192.168.122.1",
                "hostname-domain": "rdu2.scalelab.redhat.com",
                "hostname-fqdn": "controller.example.com",
                "hostname-ip-address": "10.1.36.93",
                "hostname-nis": "hostname: Local domain name not set",
                "hostname-short": "controller",
                "rpm-version": "v0.71.0-3g85910732a",
                "tools": "vmstat",
                "vmstat": "--interval=3"
            }
        }
    ],
    "runMetadata": {
        "controller": "controller.example.com",
        "controller_dir": "controller.example.com",
        "date": "2023-03-23T20:26:03",
        "end": "2023-03-23T20:26:13.177673",
        "file-date": "2023-03-23T20:27:12.376720",
        "file-name": "/srv/pbench/archive/fs-version-001/controller.example.com/pbench-user-benchmark__2023.03.23T20.26.03.tar.xz",
        "file-size": 12804,
        "hostname_f": "controller.example.com",
        "hostname_ip": "10.1.36.93, 172.21.63.246, 10.1.63.92, 192.168.122.1",
        "hostname_s": "f09-h29-b01-5039ms",
        "id": "001ab7f04079f620f6f624b6eea913df",
        "iterations": "1-default",
        "md5": "001ab7f04079f620f6f624b6eea913df",
        "name": "pbench-user-benchmark__2023.03.23T20.26.03",
        "pbench-agent-version": "v0.71.0-3g85910732a",
        "raw_size": 265692,
        "result-prefix": "spc",
        "script": "pbench-user-benchmark",
        "start": "2023-03-23T20:26:05.949697",
        "tar-ball-creation-timestamp": "2023-03-23T20:26:16.755310",
        "toc-prefix": "pbench-user-benchmark__2023.03.23T20.26.03",
        "toolsgroup": "default",
        "user": "agent"
    },
    "serverMetadata": {
        "dataset.access": "public"
    }
}
```
