# OPENID URLS
URL_REALM = "realms/{realm-name}"
URL_WELL_KNOWN = "realms/{realm-name}/.well-known/openid-configuration"
URL_TOKEN = "realms/{realm-name}/protocol/openid-connect/token"
URL_USERINFO = "realms/{realm-name}/protocol/openid-connect/userinfo"
URL_LOGOUT = "realms/{realm-name}/protocol/openid-connect/logout"
URL_INTROSPECT = "realms/{realm-name}/protocol/openid-connect/token/introspect"

# Admin URIs
URL_ADMIN_SERVER_INFO = "admin/serverinfo"
URL_ADMIN_KEYS = "admin/realms/{realm-name}/keys"
URL_ADMIN_CLIENTS = "admin/realms/{realm-name}/clients"
URL_ADMIN_CLIENT = URL_ADMIN_CLIENTS + "/{id}"
URL_ADMIN_CLIENT_ALL_SESSIONS = URL_ADMIN_CLIENT + "/user-sessions"
URL_ADMIN_CLIENT_ROLES = URL_ADMIN_CLIENT + "/roles"
URL_ADMIN_USERS = "admin/realms/{realm-name}/users"
URL_ADMIN_USER = "admin/realms/{realm-name}/users/{id}"
URL_ADMIN_GET_SESSIONS = "admin/realms/{realm-name}/users/{id}/sessions"
URL_ADMIN_REALM_ROLES = "admin/realms/{realm-name}/roles"
URL_ADMIN_USER_REALM_ROLES = "admin/realms/{realm-name}/users/{id}/role-mappings/realm"
URL_ADMIN_USER_CLIENT_ROLES = (
    "admin/realms/{realm-name}/users/{id}/role-mappings/clients/{client-id}"
)
URL_ADMIN_CLIENT_ROLE_MEMBERS = URL_ADMIN_CLIENT + "/roles/{role-name}/users"
URL_ADMIN_REALM_ROLES_MEMBERS = URL_ADMIN_REALM_ROLES + "/{role-name}/users"
