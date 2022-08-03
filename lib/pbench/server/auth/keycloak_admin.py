from typing import Dict, List
from http import HTTPStatus

import pbench.server.auth.auth_provider_urls as auth_urls
from pbench.server.auth import KeycloakOpenID


class Admin(KeycloakOpenID):
    def __init__(
        self,
        server_url: str,
        realm_name: str,
        client_id: str,
        logger,
        client_secret_key: str = None,
        verify: bool = True,
        headers: Dict = None,
        timeout: int = 60,
        user_realm: str = None,
    ):
        super().__init__(
            server_url,
            realm_name,
            client_id,
            logger,
            client_secret_key,
            verify,
            headers,
            timeout,
        )
        self.user_realm = user_realm

    def get_admin_keys(self, realm_name: str) -> List:
        """
        Return a list of keys, filtered according to query parameters
        KeysMetadataRepresentation
        https://www.keycloak.org/docs-api/18.0/rest-api/index.html#_key_resource
        :return: keys list
        """
        params_path = {"realm-name": realm_name if realm_name else self.user_realm}
        keys = self._get(
            auth_urls.URL_ADMIN_KEYS.format(**params_path), data=None
        ).json()
        return keys

    def get_client(self, client_name: str, realm: str = None) -> Dict:
        """
        Returns a keycloak client representation
        https://www.keycloak.org/docs-api/18.0/rest-api/index.html#_clientrepresentation
        :param client_name: name of the keycloak client
        :param realm: optional realm name
        :return:
        """
        params_path = {
            "realm-name": realm if realm else self.user_realm,
            "id": client_name,
        }
        return self._get(auth_urls.URL_ADMIN_CLIENT.format(**params_path)).json()

    def get_client_all_sessions(self, client_id: str, realm: str = None) -> List[Dict]:
        """
        Get sessions associated with the client.
        http://www.keycloak.org/docs-api/18.0/rest-api/index.html#_usersessionrepresentation
        :return: UserSessionRepresentation
        e.g.
        [{'id': '185481e0-dc03-41ee-be64-19b569a580f5',
        'username': 'test',
        'usderId': 'facc323e-5228-42bd-bc74-9f5f402176a2',
        'ipAdress': '10.22.18.174',
        'start': 1659394065000,
        'lastAccess': 1659394065000,
        'clients': {'d98aa03e-a258-446b-8ebd-9d91116a8d8f': 'account-console'}}]
        """
        params_path = {
            "realm-name": realm if realm else self.user_realm,
            "id": client_id,
        }
        sessions = self._get(
            auth_urls.URL_ADMIN_CLIENT_ALL_SESSIONS.format(**params_path)
        ).json()
        return sessions

    def get_all_user_sessions(self, user_id: str, realm: str = None) -> List[Dict]:
        """
        Get all the sessions associated with the user.
        :param user_id: id of the user, not the username
        :param realm: optional realm id
        https://www.keycloak.org/docs-api/18.0/rest-api/index.html#_usersessionrepresentation
        :return: UserSessionRepresentation
        e.g:
        [{'id': '185481e0-dc03-41ee-be64-19b569a580f5',
        'username': 'test',
        'usderId': 'facc323e-5228-42bd-bc74-9f5f402176a2',
        'ipAdress': '10.22.18.174',
        'start': 1659394065000,
        'lastAccess': 1659394065000,
        'clients': {'d98aa03e-a258-446b-8ebd-9d91116a8d8f': 'account-console'}}]
        """
        params_path = {"realm-name": realm if realm else self.realm_name, "id": user_id}
        return self._get(auth_urls.URL_ADMIN_GET_SESSIONS.format(**params_path)).json()

    def get_client_sessions_count(self, client_id: str, realm_name: str = None) -> Dict:
        """
        Get all sessions count for the given client
        :param client_id: id of the client (not client-id)
        :param realm_name: optional realm name
        :return: { "count": number }
        """
        params_path = {
            "realm-name": realm_name if realm_name else self.user_realm,
            "id": client_id,
        }
        return self._get(
            auth_urls.URL_ADMIN_CLIENT_SESSIONS_COUNT.format(**params_path)
        ).json()

    def logout_user_sessions(self, user_id: str, realm_name: str = None) -> HTTPStatus:
        """
        log the user out of all the sessions
        :param user_id: id of the user
        :param realm_name: optional realm name
        :return:
        """
        params_path = {
            "realm-name": realm_name if realm_name else self.user_realm,
            "id": user_id,
        }
        return HTTPStatus(
            self._post(
                auth_urls.URL_ADMIN_USER_LOGOUT.format(**params_path), data=""
            ).status_code
        )

    def realm_all_sessions_logout(self, realm_name: str = None) -> HTTPStatus:
        """
        Logout all the sessions under the given realm
        :param realm_name:
        :return:
        """
        params_path = {"realm-name": realm_name if realm_name else self.user_realm}
        return HTTPStatus(
            self._post(
                auth_urls.URL_ADMIN_REALM_SESSIONS_LOGOUT.format(**params_path), data={}
            ).status_code
        )

    def get_all_users(self, realm_name: str = None, params: Dict = None) -> List[Dict]:
        """
        Get all the users.
        Return a list of users, filtered according to query parameters
        https://www.keycloak.org/docs-api/18.0/rest-api/index.html#_userrepresentation
        :param realm_name: name of the realm for which all the users will be queried
        :param params: Query parameters (optional)
        :return: users list
        """
        params = params or {}
        params_path = {"realm_name": realm_name if realm_name else self.user_realm}
        return self._get(
            auth_urls.URL_ADMIN_USERS.format(**params_path), **params
        ).json()

    def count_users(self, realm_name: str = None, params: Dict = None) -> Dict:
        """
        Count all the users for the given realm
        :param realm_name:
        :param params: Any filtering params to apply
        :return:{ "count": number }
        """
        params = params or {}
        params_path = {"realm_name": realm_name if realm_name else self.user_realm}
        return self._get(
            auth_urls.URL_ADMIN_USERS_COUNT.format(**params_path), **params
        ).json()

    def get_user(self, user_id: str, realm: str = None) -> Dict:
        """
        Get representation of the user.
        :param user_id: id of the user, not the username
        https://www.keycloak.org/docs-api/18.0/rest-api/index.html#_userrepresentation
        :return: UserRepresentation
        """
        params_path = {"realm-name": realm if realm else self.user_realm, "id": user_id}
        return self._get(auth_urls.URL_ADMIN_USER.format(**params_path)).json()

    def get_user_id(self, username: str):
        """
        Get internal keycloak user id from username.
        This is required for further actions against this user.
        https://www.keycloak.org/docs-api/18.0/rest-api/index.html#_userrepresentation
        :param username: user registered username
        :return: user_id
        """
        lower_user_name = username.lower()
        user = self.get_all_users(params={"username": lower_user_name})[0]
        return user["id"]

    def create_user(self, payload: Dict, exist_ok: bool) -> Dict:
        """
        Create a new user.
        Username must be unique
        https://www.keycloak.org/docs-api/18.0/rest-api/index.html#_userrepresentation
        :param payload: UserRepresentation
        :param exist_ok: If False, raise KeycloakError if username already exists.
                        Otherwise, return existing user ID.
        :return: UserRepresentation
        """
        params_path = {"realm-name": self.user_realm}

        if exist_ok:
            user_id = self.get_user_id(username=payload["username"])

            if user_id is not None:
                return self.get_user(user_id, self.user_realm)

        self.add_header_param(key="Content-Type", value="application/json")
        return self._post(
            auth_urls.URL_ADMIN_USERS.format(**params_path), data=payload
        ).json()

    def delete_user(self, user_id: str) -> HTTPStatus:
        """
        Delete the given user entry
        :param user_id: id of the user
        :return:
        """
        params_path = {"realm-name": self.user_realm, "id": user_id}
        return HTTPStatus(
            self._delete(auth_urls.URL_ADMIN_USER.format(**params_path)).status_code
        )

    def update_user(self, user_id: str, payload: Dict) -> HTTPStatus:
        """
        Update the given user with payload data
        https://www.keycloak.org/docs-api/18.0/rest-api/index.html#_userrepresentation
        :param user_id: id of the user
        :param payload: UserRepresentation
        :return:
        """
        params_path = {"realm-name": self.realm_name, "id": user_id}
        self.add_header_param(key="Content-Type", value="application/json")
        return HTTPStatus(
            self._put(
                auth_urls.URL_ADMIN_USER.format(**params_path), data=payload
            ).status_code
        )

    def realm_client_roles(self, realm: str = None, client_id: str = None) -> Dict:
        """
        Get all roles for the given realm and client.
        If the client is not specified this will return all the roles under the realm
        :param realm: realm id
        :param client_id: id of the client, not the client name
        https://www.keycloak.org/docs-api/18.0/rest-api/index.html#_rolerepresentation
        :return: Keycloak server response (RoleRepresentation)
        """
        if not client_id:
            params_path = {"realm-name": realm if realm else self.user_realm}
            return self._get(
                auth_urls.URL_ADMIN_REALM_ROLES.format(**params_path)
            ).json()
        else:
            params_path = {
                "realm-name": realm if realm else self.user_realm,
                "client_id": client_id,
            }
            return self._get(
                auth_urls.URL_ADMIN_CLIENT_ROLES.format(**params_path)
            ).json()

    def get_realm_client_role_members(
        self,
        role_name: str,
        realm: str = None,
        client_id: str = None,
        params: Dict = None,
    ):
        """
        Get all the members of the given role of the realm.
        :param role_name: Name of the role.
        :param realm: optional realm name
        :param client_id: optional id of client
        :param params: Additional Query parameters
            (see https://www.keycloak.org/docs-api/18.0/rest-api/index.html#_roles_resource)
        :return: Keycloak Server Response (UserRepresentation)
        """
        params = params or dict()
        if not client_id:
            params_path = {
                "realm-name": realm if realm else self.user_realm,
                "role-name": role_name,
            }
            return self._get(
                auth_urls.URL_ADMIN_REALM_ROLES_MEMBERS.format(**params_path), **params
            ).json()
        else:
            params_path = {
                "realm-name": realm if realm else self.user_realm,
                "id": client_id,
                "role-name": role_name,
            }
            return self._get(
                auth_urls.URL_ADMIN_CLIENT_ROLE_MEMBERS.format(**params_path), **params
            ).json()

    def get_user_realm_client_roles(
        self, user_id: str, realm: str = None, client_id: str = None
    ) -> Dict:
        """
        Get all realm/client roles for a user.
        :param user_id: id of user
        :param realm: optional realm name
        :param client_id: optional id of the client
        :return: Keycloak list of RoleRepresentation
        """
        if not client_id:
            params_path = {
                "realm-name": realm if realm else self.user_realm,
                "id": user_id,
            }
            return self._get(
                auth_urls.URL_ADMIN_USER_REALM_ROLES.format(**params_path)
            ).json()
        else:
            params_path = {
                "realm-name": realm if realm else self.user_realm,
                "id": user_id,
                "client_id": client_id,
            }
            return self._get(
                auth_urls.URL_ADMIN_USER_CLIENT_ROLES.format(**params_path)
            ).json()
