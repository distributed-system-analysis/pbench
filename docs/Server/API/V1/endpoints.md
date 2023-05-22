# `GET /api/v1/endpoints`

This API describes the set of URI endpoints available under the Pbench Server
V1 API, the Keycloak broker configuration for authorization, and the current
Pbench Server version identification.

This API does not require authentication and has no access restrictions.

## Response status

`200`   **OK** \
Successful request.

## Response headers

`content-type: application/json` \
The return is a JSON document containing the summary "run" data from the
dataset index.

## Response body

The `application/json` response body is a JSON object describing the Pbench
Server configuration.

The information is divided into four sections, as described below.

### `identification`

This identifies the name and version of the Pbench Server.

### `openid`

The Pench Server authenticates through an OIDC broker (e.g., Keycloak). In order
to authenticate and receive an authorization token to present to server APIs, the
client must redirect to the broker login page using the `server_url` given here,
with the Pbench Server `realm` and `client` ID.

### `uri`

A representation of the Pbench Server APIs supported on this server.

#### Name

The "name" of the API. For example, to query or set metadata for a dataset,
`endpoints.uri.dataset_metadata` would return a JSON object describing the
URI template and parameters for the API.

##### `template`

The API's URI template pattern, with URI parameters in the form `{<name>}`, as in
`http://host:port/api/v1/datasets/{dataset}/metadata`.

##### `params`

A sub-object describing the URI parameters referenced in the URI template. Each
param has a name and type. Note that "type" refers to the Flask URI parsing, and
the main useful distinction here is that `string` means a simple undeliminated
string whereas `path` refers to a `/`-separated string that resembles a UNIX file
path.

Each param name appears in the template in the form `{<name>}`, which is a convenient
format for the Python `format` function.

```python
    uri = endpoints["uri"]["datasets_metadata"]["template"].format(dataset=id)
```

A similar formatter can be built easily for Javascript:

```javascript
/**
 * Expand a templated API URI like a Python `.format`
 *
 * @param {Object} endpoints - endpoint object from server
 * @param {string} name - name of the API to expand
 * @param {Object} args - value for each templated parameter
 * @return {string} - formatted URI
 */
export const uriTemplate = (endpoints, name, args) => {
  return Object.entries(args).reduce(
    (uri, [key, value]) => uri.replace(`{${key}}`, value),
    endpoints.uri[name].template
  );
};

let uri = uriTemplate(
    endpoints,
    'datasets_metadata',
    {dataset: resource_id}
    );
```

```json
{
    "identification": "Pbench server 1.0.0-85189370c",
    "openid": {
        "uri": "openid.example.com",
        "pbench-client": "client name"
    },
    "uri": {
        "datasets": {
            "params": {
                "dataset": {
                    "type": "string"
                }
            },
            "template": "http://10.1.1.1:8080/api/v1/datasets/{dataset}"
        },
        "datasets_contents": {
            "params": {
                "dataset": {
                    "type": "string"
                },
                "target": {
                    "type": "path"
                }
            },
            "template": "http://10.1.1.1:8080/api/v1/datasets/{dataset}/contents/{target}"
        },
        "datasets_daterange": {
            "params": {},
            "template": "http://10.1.1.1:8080/api/v1/datasets/daterange"
        },
        "datasets_detail": {
            "params": {
                "dataset": {
                    "type": "string"
                }
            },
            "template": "http://10.1.1.1:8080/api/v1/datasets/{dataset}/detail"
        },
        "datasets_inventory": {
            "params": {
                "dataset": {
                    "type": "string"
                },
                "target": {
                    "type": "path"
                }
            },
            "template": "http://10.1.1.1:8080/api/v1/datasets/{dataset}/inventory/{target}"
        },
        "datasets_list": {
            "params": {},
            "template": "http://10.1.1.1:8080/api/v1/datasets"
        },
        "datasets_mappings": {
            "params": {
                "dataset_view": {
                    "type": "string"
                }
            },
            "template": "http://10.1.1.1:8080/api/v1/datasets/mappings/{dataset_view}"
        },
        "datasets_metadata": {
            "params": {
                "dataset": {
                    "type": "string"
                }
            },
            "template": "http://10.1.1.1:8080/api/v1/datasets/{dataset}/metadata"
        },
        "datasets_namespace": {
            "params": {
                "dataset": {
                    "type": "string"
                },
                "dataset_view": {
                    "type": "string"
                }
            },
            "template": "http://10.1.1.1:8080/api/v1/datasets/{dataset}/namespace/{dataset_view}"
        },
        "datasets_search": {
            "params": {},
            "template": "http://10.1.1.1:8080/api/v1/datasets/search"
        },
        "datasets_values": {
            "params": {
                "dataset": {
                    "type": "string"
                },
                "dataset_view": {
                    "type": "string"
                }
            },
            "template": "http://10.1.1.1:8080/api/v1/datasets/{dataset}/values/{dataset_view}"
        },
        "endpoints": {
            "params": {},
            "template": "http://10.1.1.1:8080/api/v1/endpoints"
        },
        "login": {
            "params": {},
            "template": "http://10.1.1.1:8080/api/v1/login"
        },
        "logout": {
            "params": {},
            "template": "http://10.1.1.1:8080/api/v1/logout"
        },
        "register": {
            "params": {},
            "template": "http://10.1.1.1:8080/api/v1/register"
        },
        "server_audit": {
            "params": {},
            "template": "http://10.1.1.1:8080/api/v1/server/audit"
        },
        "server_settings": {
            "params": {
                "key": {
                    "type": "string"
                }
            },
            "template": "http://10.1.1.1:8080/api/v1/server/settings/{key}"
        },
        "upload": {
            "params": {
                "filename": {
                    "type": "string"
                }
            },
            "template": "http://10.1.1.1:8080/api/v1/upload/{filename}"
        },
        "user": {
            "params": {
                "target_username": {
                    "type": "string"
                }
            },
            "template": "http://10.1.1.1:8080/api/v1/user/{target_username}"
        }
    }
}
```
