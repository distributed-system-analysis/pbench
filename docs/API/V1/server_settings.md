# `GET /api/v1/server/settings[/][{key}]`

This API returns an `application/json` document describing the Pbench Server
settings. When the `{key}` parameter is specified, the API will return the
specific named server setting. When `{key}` is omitted, all server settings will
be returned.

## Query parameters

None.

## Request headers

`authorization: bearer` token [_optional_] \
*Bearer* schema authorization may be specified, but is not required to `GET`
server settings.

## Response headers

`content-type: application/json` \
The return is a serialized JSON object with the requested server settings.

## Response status

`400`   **BAD REQUEST** \
The specified `{key}` value (see [settings](#server-settings))
is unknown.

## Response body

The `application/json` response body is a JSON document containing the requested
server setting key and value or, if no `{key}` was specified, all supported
server settings.

### Examples

```python
GET /api/v1/server/settings/dataset-lifetime
{
    "dataset-lifetime": "4"
}

GET /api/v1/server/settings/
{
    "dataset-lifetime": "4",
    "server-banner": {
        "message": "Server will be down for maintenance on Tuesday!",
        "contact": "admin@lab.example.com"
    }
    "server-state": {
        "status": "readonly",
        "message": "rebuilding index ... back to normal soon"
    }
}
```

# `PUT /api/v1/server/settings[/][{key}]`

This API allows a user holding the `ADMIN` role to modify server settings. When
the `{key}` parameter is specified, the API will modify a single named setting.
When `{key}` is omitted, the `application/json` request body can be used to
modify multiple server settings at once.

## Query parameters

`value`    string \
When a single server setting is specified with `{key}` in the URI, you can
specify a string value for the parameter using this query parameter without an
`application/json` request body. For example, `PUT /api/v1/server/settings/key?value=1`.

You cannot specify complex JSON server settings this way. Instead, use the
`value` field in the `application/json` request body.

## Request body

When specifying a complex JSON value for a server setting, or when specifying
multiple server settings, the data to be set is specified in an
`application/json` request body.

You can specify a single `{key}` in the URI and then specify the value
using a `value` field in the `application/json` request body instead of using
the `value` query parameter. You can do this even if the value is a simple
string, although it's more useful when you need to specify a JSON object value.
For example,

```python
PUT /api/v1/server/settings/server-state
{
    "value": {"status": "enabled"}
}
```

If you omit the `{key}` value from the URI, specify all server settings you wish
to change in the `application/json` request body. You can specify a single
server setting, or any group of server settings at once. For example,

```python
PUT /api/v1/server/settings/
{
    "server-state": {"status": "disabled", "message": "down for maintenance"},
    "server-banner": {"message": "Days of 100% uptime: 0"}
}
```

## Request headers

`authorization: bearer` token \
*Bearer* schema authorization is required to change any server settings. The
authenticated user must have `ADMIN` role.

## Response headers

`content-type: application/json` \
The response body is a serialized JSON object with the selected server settings.

## Response status

`401`   **UNAUTHORIZED** \
The client is attempting to change server settings with `PUT` and did not
provide an authentication token.

`403`   **FORBIDDEN** \
The client is attempting to change server settings with `PUT` and the provided
authentication token does not correspond to a user with `ADMIN` role.

## Response body

The `application/json` response body for `PUT` is exactly the same as for
[`GET`](#response-body) when the same server settings are requested, showing
only the server settings that were changed in the `PUT`.

_This request:_
```python
PUT /api/v1/server/settings/dataset-lifetime?value=4
```

_returns this response:_
```python
{
    "dataset-lifetime": "4"
}
```


_And this request:_
```python
PUT /api/v1/server/settings
{
    "dataset-lifetime": "4 days",
    "server-state": {"status": "enabled"}
}
```

_returns this response:_
```python
{
    "dataset-lifetime": "4",
    "server-state": {"status": "enabled"}
}
```

## Server settings

### dataset-lifetime

The value for the `dataset-lifetime` server setting is the *maximum* number of
days a dataset can be retained on the server. When each dataset is uploaded to
the server, a "deletion date" represented by the dataset [metadata](../metadata.md)
key `server.deletion` is calculated based on this value and user preferences
(which may specify a shorter lifetime, but not a longer lifetime). When a
dataset has remained on the server past the `server.deletion` date, it may be
removed automatically by the server to conserve space.

The number of days is specified as an string representing an integer, optionally
followed by a space and `day` or `days`. For example, "4" or "4 days" or "4 day"
are equivalent.

```python
{
    "dataset-lifetime": "4"
}
```

### server-banner

This server setting allows a server administrator to set an informational
message that can be retrieved and displayed by any client, for example as a
banner on a UI. The value is a JSON object, containing at least a `message`
field.

Any additional JSON data may be provided. The server will store the entire
JSON object and return it when a client requests it with
`GET /api/v1/server/settings/server-banner`. The server will not interpret
any information in this JSON object.

For example, the following are examples of valid banners:

```python
{
    "server-banner": {
        "message": "Have a Happy Pbench Day"
    }
}
```

```python
{
    "server-banner": {
        "message": "The server will be down for 2 hours on Monday, July 31",
        "contact": {
            "email": "admin@pbench.example.com",
            "phone": "(555) 555-5555",
            "hours": ["8:00 EST", "17:00 EST"]
        },
        "statistics": {
            "datasets": 50000,
            "hours-up": 2.3,
            "users": 26
        }
    }
}
```

### server-state

This server setting allows a server administrator to control the operating state
of the server remotely. As for [`server-banner`](#server-banner), the value is a
JSON object, and any JSON fields passed in to the server will be returned to a
client. The following fields have special meaning:

**`status`** \
The operating status of the server.

* `enabled`: Normal operation.
* `disabled`: Most server API endpoints will fail with the **503** (service
unavailable) HTTP status. However a few endpoints are always allowed:
  * [endpoints](./endpoints.md) for server settings information;
  * [login](./login.md) because only an authenticated user with `ADMIN` role
    can modify server settings;
  * [logout](./logout.md) for consistency;
  * [server_settings](./server_settings.md) to allow re-enabling the server
    or modifying the banner.
* `readonly`: The server will respond to `GET` requests for information, but
will return **503** (service unavailable) for any attempt to modify server
state. (With the same exceptions as listed above for `disabled`.)

**`message`** \
A message to explain downtime. This is required when the `status` is `disabled`
or `readonly` and optional otherwise.

When the server status is `disabled`, or when it's `readonly` and a client
tries to modify some data through the API, the server will fail the request
with a `503` (service unavailable) error. It will return an `application/json`
error response payload containing the full `server-state` JSON object. The
`message` key in an error response is a standard convention, and many clients
will display this as an explanation for the failure. The client will also have
access to any additional information provided in the `server-state` JSON object.

Note that you can set a `message` when the `status` is `enabled` but it won't
be reported to a client unless a client asks for the `server-state` setting. The
`server-state` message is intended to explain server downtime when an API call
fails. The `server-banner` setting is generally more appropriate to provide
client information under normal operating conditions.
