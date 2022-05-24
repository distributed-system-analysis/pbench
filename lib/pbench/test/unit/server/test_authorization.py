from typing import Union

import pytest

from pbench.server.api.auth import Auth
from pbench.server.api.resources import (
    API_METHOD,
    ApiBase,
    API_OPERATION,
    ApiSchema,
    UnauthorizedAccess,
)
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
            client.config, client.logger, ApiSchema(API_METHOD.GET, API_OPERATION.READ)
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
            {"user": "drb", "access": "private", "role": API_OPERATION.UPDATE},
            {"user": "drb", "access": "public", "role": API_OPERATION.UPDATE},
            {"user": "drb", "access": "private", "role": API_OPERATION.DELETE},
            {"user": "drb", "access": "public", "role": API_OPERATION.DELETE},
            {"user": "drb", "access": "private", "role": API_OPERATION.READ},
            {"user": "drb", "access": "public", "role": API_OPERATION.READ},
            {"user": None, "access": "private", "role": API_OPERATION.READ},
            {"user": None, "access": "public", "role": API_OPERATION.READ},
        ],
    )
    def test_allowed_admin(
        self, apibase, server_config, create_drb_user, current_user_admin, ask
    ):
        user = self.get_user_id(ask["user"])
        apibase._check_authorization(user, ask["access"], ask["role"])

    @pytest.mark.parametrize(
        "ask",
        [
            {"user": None, "access": "private", "role": API_OPERATION.UPDATE},
            {"user": None, "access": "public", "role": API_OPERATION.UPDATE},
            {"user": None, "access": "private", "role": API_OPERATION.DELETE},
            {"user": None, "access": "public", "role": API_OPERATION.DELETE},
        ],
    )
    def test_disallowed_admin(self, apibase, server_config, current_user_admin, ask):
        user = self.get_user_id(ask["user"])
        access = ask["access"]
        with pytest.raises(UnauthorizedAccess) as exc:
            apibase._check_authorization(user, access, ask["role"])
        assert exc.value.owner == (ask["user"] if ask["user"] else "none")
        assert exc.value.user == current_user_admin

    @pytest.mark.parametrize(
        "ask",
        [
            {"user": "drb", "access": "private", "role": API_OPERATION.UPDATE},
            {"user": "drb", "access": "public", "role": API_OPERATION.UPDATE},
            {"user": "drb", "access": "private", "role": API_OPERATION.DELETE},
            {"user": "drb", "access": "public", "role": API_OPERATION.DELETE},
            {"user": "drb", "access": "private", "role": API_OPERATION.READ},
            {"user": "drb", "access": "public", "role": API_OPERATION.READ},
            {"user": "test", "access": "public", "role": API_OPERATION.READ},
            {"user": None, "access": "public", "role": API_OPERATION.READ},
            {"user": None, "access": "private", "role": API_OPERATION.READ},
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
        apibase._check_authorization(user, ask["access"], ask["role"])

    @pytest.mark.parametrize(
        "ask",
        [
            {"user": "test", "access": "private", "role": API_OPERATION.UPDATE},
            {"user": "test", "access": "public", "role": API_OPERATION.UPDATE},
            {"user": None, "access": "private", "role": API_OPERATION.UPDATE},
            {"user": None, "access": "public", "role": API_OPERATION.UPDATE},
            {"user": "test", "access": "private", "role": API_OPERATION.DELETE},
            {"user": "test", "access": "public", "role": API_OPERATION.DELETE},
            {"user": None, "access": "private", "role": API_OPERATION.DELETE},
            {"user": None, "access": "public", "role": API_OPERATION.DELETE},
            {"user": "test", "access": "private", "role": API_OPERATION.READ},
        ],
    )
    def test_disallowed_auth(
        self, apibase, server_config, create_user, current_user_drb, ask
    ):
        user = self.get_user_id(ask["user"])
        access = ask["access"]
        with pytest.raises(UnauthorizedAccess) as exc:
            apibase._check_authorization(user, access, ask["role"])
        assert exc.value.owner == (ask["user"] if ask["user"] else "none")
        assert exc.value.user == current_user_drb

    @pytest.mark.parametrize(
        "ask",
        [
            {"user": "drb", "access": "public", "role": API_OPERATION.READ},
            {"user": "test", "access": "public", "role": API_OPERATION.READ},
            {"user": None, "access": "public", "role": API_OPERATION.READ},
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
        apibase._check_authorization(user, ask["access"], ask["role"])

    @pytest.mark.parametrize(
        "ask",
        [
            {"user": "test", "access": "private", "role": API_OPERATION.UPDATE},
            {"user": "test", "access": "public", "role": API_OPERATION.UPDATE},
            {"user": "test", "access": "private", "role": API_OPERATION.DELETE},
            {"user": "test", "access": "public", "role": API_OPERATION.DELETE},
            {"user": "test", "access": "private", "role": API_OPERATION.READ},
        ],
    )
    def test_disallowed_noauth(
        self, apibase, server_config, create_user, current_user_none, ask
    ):
        user = self.get_user_id(ask["user"])
        access = ask["access"]
        with pytest.raises(UnauthorizedAccess) as exc:
            apibase._check_authorization(user, access, ask["role"])
        assert exc.value.owner == (ask["user"] if ask["user"] else "none")
        assert exc.value.user is None
