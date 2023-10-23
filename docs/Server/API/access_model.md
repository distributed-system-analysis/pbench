# Access model

The Pbench Server employs a simple REST-style "CRUD" model for authorizing
resource access.

* CREATE enables the ability to create a new instance of a specific resource.
* READ enables the ability to read (but not modify) an existing instance of a
specific resource.
* UPDATE enables the ability to modify an existing instance of a specific resource.
* DELETE enables the ability to delete an existing instance of a specific resource.

The *owner* of a resource always has full CRUD access to that resource.

A user with the administrator *role* always has full CRUD access to all resources.

Any client, regardless of authentication, is able to READ a dataset with the
`access` property set to `"public"`. Only the owner of the dataset, or a user with
the administrator *role*, can UPDATE or DELETE the dataset.

## User Identity

The Pbench Server works with an external OIDC identity provider, for example
Red Hat, Google, or GitHub SSO. The Pbench Server authenticates user access using
the OIDC JWT tokens. The token's encoded `sub` field is the primary "user ID"
controlling ownership of and access to data. The token's `preferred_username`
field will be remembered and used when trying to report the "user ID" in human
readable form.

## Roles

The Pbench Server access model allows assigning an `ADMIN` role to one or more
user accounts. These users will be granted full CRUD access to all server data,
including all datasets, server settings, and audit logs.

In Pbench Server 1.0, there are two ways to assign the `ADMIN` role to a user:

If you have administrative access to the OIDC client configuration, you cay add
the `ADMIN` role token to the audience field that will be encoded into the JWT
token under the `resource_access` field.

Or you can add the `admin-role` configuration variable in the `pbench-server`
section of the server's `/opt/pbench-server/lib/config/pbench-server.cfg` file,
set to a list of OIDC `preferred_username` values: for example,

```
[pbench-server]
admin-role = dave,webb
```

## Groups

_TBD_
