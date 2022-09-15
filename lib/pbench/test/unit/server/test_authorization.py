from typing import Union

import pytest

from pbench.server import OperationCode
from pbench.server.api.resources import (
    ApiAuthorization,
    ApiAuthorizationType,
    ApiBase,
    ApiMethod,
    ApiSchema,
    UnauthorizedAccess,
)
from pbench.server.auth.auth import Auth
from pbench.server.database.models.users import User


class TestAuthorization:
    def get_user_id(self, user: Union[str, None]) -> Union[str, None]:
        if user:
            userdb = User.query(username=user)
            if userdb:
                user = str(userdb.id)
            else:
                print(f"\nUnknown user {user}\n")
                user = None
        return user

    @pytest.fixture()
    def apibase(self, client) -> ApiBase:
        return ApiBase(
            client.config, client.logger, ApiSchema(ApiMethod.GET, OperationCode.READ)
        )

    @pytest.fixture()
    def current_user_admin(self, monkeypatch):
        admin_user = User(
            email="email@example.com",
            id=6,
            username="admin",
            first_name="Test",
            last_name="Admin",
            role="admin",
        )

        class FakeHTTPTokenAuth:
            def current_user(self) -> User:
                return admin_user

        with monkeypatch.context() as m:
            m.setattr(Auth, "token_auth", FakeHTTPTokenAuth())
            yield admin_user

    @pytest.mark.parametrize(
        "ask",
        [
            {"user": "drb", "access": "private", "role": OperationCode.UPDATE},
            {"user": "drb", "access": "public", "role": OperationCode.UPDATE},
            {"user": "drb", "access": "private", "role": OperationCode.DELETE},
            {"user": "drb", "access": "public", "role": OperationCode.DELETE},
            {"user": "drb", "access": "private", "role": OperationCode.READ},
            {"user": "drb", "access": "public", "role": OperationCode.READ},
            {"user": None, "access": "private", "role": OperationCode.READ},
            {"user": None, "access": "public", "role": OperationCode.READ},
        ],
    )
    def test_allowed_admin(
        self, apibase, server_config, create_drb_user, current_user_admin, ask
    ):
        user = self.get_user_id(ask["user"])
        apibase._check_authorization(
            ApiAuthorization(
                ApiAuthorizationType.USER_ACCESS, ask["role"], user, ask["access"]
            )
        )

    @pytest.mark.parametrize(
        "ask",
        [
            {"user": None, "access": "private", "role": OperationCode.UPDATE},
            {"user": None, "access": "public", "role": OperationCode.UPDATE},
            {"user": None, "access": "private", "role": OperationCode.DELETE},
            {"user": None, "access": "public", "role": OperationCode.DELETE},
        ],
    )
    def test_disallowed_admin(self, apibase, server_config, current_user_admin, ask):
        user = self.get_user_id(ask["user"])
        access = ask["access"]
        with pytest.raises(UnauthorizedAccess) as exc:
            apibase._check_authorization(
                ApiAuthorization(
                    ApiAuthorizationType.USER_ACCESS, ask["role"], user, access
                )
            )
        assert exc.value.owner == (ask["user"] if ask["user"] else "none")
        assert exc.value.user == current_user_admin

    @pytest.mark.parametrize(
        "ask",
        [
            {"user": "drb", "access": "private", "role": OperationCode.UPDATE},
            {"user": "drb", "access": "public", "role": OperationCode.UPDATE},
            {"user": "drb", "access": "private", "role": OperationCode.DELETE},
            {"user": "drb", "access": "public", "role": OperationCode.DELETE},
            {"user": "drb", "access": "private", "role": OperationCode.READ},
            {"user": "drb", "access": "public", "role": OperationCode.READ},
            {"user": "test", "access": "public", "role": OperationCode.READ},
            {"user": None, "access": "public", "role": OperationCode.READ},
            {"user": None, "access": "private", "role": OperationCode.READ},
        ],
    )
    def test_allowed_auth(
        self,
        apibase,
        server_config,
        create_user,
        create_drb_user,
        current_user_drb,
        ask,
    ):
        user = self.get_user_id(ask["user"])
        apibase._check_authorization(
            ApiAuthorization(
                ApiAuthorizationType.USER_ACCESS, ask["role"], user, ask["access"]
            )
        )

    @pytest.mark.parametrize(
        "ask",
        [
            {"user": "test", "access": "private", "role": OperationCode.UPDATE},
            {"user": "test", "access": "public", "role": OperationCode.UPDATE},
            {"user": None, "access": "private", "role": OperationCode.UPDATE},
            {"user": None, "access": "public", "role": OperationCode.UPDATE},
            {"user": "test", "access": "private", "role": OperationCode.DELETE},
            {"user": "test", "access": "public", "role": OperationCode.DELETE},
            {"user": None, "access": "private", "role": OperationCode.DELETE},
            {"user": None, "access": "public", "role": OperationCode.DELETE},
            {"user": "test", "access": "private", "role": OperationCode.READ},
        ],
    )
    def test_disallowed_auth(
        self, apibase, server_config, create_user, current_user_drb, ask
    ):
        user = self.get_user_id(ask["user"])
        access = ask["access"]
        with pytest.raises(UnauthorizedAccess) as exc:
            apibase._check_authorization(
                ApiAuthorization(
                    ApiAuthorizationType.USER_ACCESS, ask["role"], user, access
                )
            )
        assert exc.value.owner == (ask["user"] if ask["user"] else "none")
        assert exc.value.user == current_user_drb

    @pytest.mark.parametrize(
        "ask",
        [
            {"user": "drb", "access": "public", "role": OperationCode.READ},
            {"user": "test", "access": "public", "role": OperationCode.READ},
            {"user": None, "access": "public", "role": OperationCode.READ},
        ],
    )
    def test_allowed_noauth(
        self,
        apibase,
        server_config,
        create_user,
        create_drb_user,
        current_user_none,
        ask,
    ):
        user = self.get_user_id(ask["user"])
        apibase._check_authorization(
            ApiAuthorization(
                ApiAuthorizationType.USER_ACCESS, ask["role"], user, ask["access"]
            )
        )

    @pytest.mark.parametrize(
        "ask",
        [
            {"user": "test", "access": "private", "role": OperationCode.UPDATE},
            {"user": "test", "access": "public", "role": OperationCode.UPDATE},
            {"user": "test", "access": "private", "role": OperationCode.DELETE},
            {"user": "test", "access": "public", "role": OperationCode.DELETE},
            {"user": "test", "access": "private", "role": OperationCode.READ},
        ],
    )
    def test_disallowed_noauth(
        self, apibase, server_config, create_user, current_user_none, ask
    ):
        user = self.get_user_id(ask["user"])
        access = ask["access"]
        with pytest.raises(UnauthorizedAccess) as exc:
            apibase._check_authorization(
                ApiAuthorization(
                    ApiAuthorizationType.USER_ACCESS, ask["role"], user, access
                )
            )
        assert exc.value.owner == (ask["user"] if ask["user"] else "none")
        assert exc.value.user is None

    def test_admin_unauth(self, apibase, server_config, current_user_none):
        with pytest.raises(UnauthorizedAccess) as exc:
            apibase._check_authorization(
                ApiAuthorization(ApiAuthorizationType.ADMIN, OperationCode.CREATE)
            )
        assert (
            str(exc.value)
            == "Unauthenticated client is not authorized to CREATE a server administrative resource"
        )

    def test_admin_user(self, apibase, server_config, current_user_drb):
        with pytest.raises(UnauthorizedAccess) as exc:
            apibase._check_authorization(
                ApiAuthorization(ApiAuthorizationType.ADMIN, OperationCode.CREATE)
            )
        assert (
            str(exc.value)
            == "User drb is not authorized to CREATE a server administrative resource"
        )

    def test_admin_admin(self, apibase, server_config, current_user_admin):
        apibase._check_authorization(
            ApiAuthorization(ApiAuthorizationType.ADMIN, OperationCode.CREATE)
        )
