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

The Pbench Server user model allows assigning an `ADMIN` role to one or more
user accounts on the server. These users will be granted full CRUD access to
all server data, including

- All datasets
- All user profiles
- Server configuration settings

A user with the `ADMIN` role can use the [user](V1/user.md) (profile) API to
assign the `ADMIN` role to other users. On installation of the Pbench Server
there are no users with `ADMIN` role, so the server management CLI (described
elsewhere) must be used to create an administrator account or assign the `ADMIN`
role to some user.

## Groups

_TBD_