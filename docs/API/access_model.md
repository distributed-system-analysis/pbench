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

## Roles

The Pbench Server access model allows assigning an `ADMIN` role to one or more
user accounts through the OIDC identity provider. These users will be granted
full CRUD access to all server data, including all datasets, server settings,
and audit logs.

## Groups

_TBD_
