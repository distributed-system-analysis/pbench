from http import HTTPStatus
import pytest

from pbench.server.api.resources import Schema
from pbench.server.api.auth import Auth
from pbench.server.api.resources.query_apis import AssemblyError, ElasticBase, JSON
from pbench.server.database.models.users import User


USER_ID = "20"
SELF_ID = "3"  # This needs to match the current_user_drb fixture


class TestQueryBuilder:
    @pytest.fixture()
    def elasticbase(self, client):
        return ElasticBase(client.config, client.logger, Schema())

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
            ({}, {}),
            ({"access": "public"}, {"access": "public"}),
            ({"access": "private"}, {"access": "private"}),
            ({"user": USER_ID}, {"user": USER_ID}),
            (
                {"user": USER_ID, "access": "private"},
                {"user": USER_ID, "access": "private"},
            ),
            (
                {"user": USER_ID, "access": "public"},
                {"user": USER_ID, "access": "public"},
            ),
        ],
    )
    def test_admin(self, elasticbase, server_config, current_user_admin, ask):
        term = {"term": {"icecream": "ginger"}}
        query = elasticbase._get_user_query(ask[0], [term])
        filter = [term]
        if "access" in ask[1]:
            filter.append({"term": {"authorization.access": ask[1]["access"]}})
        if "user" in ask[1]:
            filter.append({"term": {"authorization.owner": ask[1]["user"]}})
        assert query == {"bool": {"filter": filter}}

    @pytest.mark.parametrize(
        "ask",
        [
            ({"access": "public"}, {"access": "public"}),
            ({"access": "private"}, {"user": SELF_ID, "access": "private"}),
            ({"user": SELF_ID}, {"user": SELF_ID}),
            ({"user": USER_ID}, {"user": USER_ID, "access": "public"}),
            (
                {"user": SELF_ID, "access": "private"},
                {"user": SELF_ID, "access": "private"},
            ),
            (
                {"user": SELF_ID, "access": "public"},
                {"user": SELF_ID, "access": "public"},
            ),
            (
                {"user": USER_ID, "access": "public"},
                {"user": USER_ID, "access": "public"},
            ),
        ],
    )
    def test_auth(self, elasticbase, server_config, current_user_drb, ask):
        """
        Test the query builder when we have an authorized user.

        NOTES:

        1) We don't test {} here: that's left to a separate test case rather
           than building the unique disjunction syntax here;
        2) We don't test {"user": USER_ID, "access": "private"} here:
           That raises the AssemblyError exception, and is tested in a
           separate test case.
        """
        term = {"term": {"icecream": "ginger"}}
        query = elasticbase._get_user_query(ask[0], [term])
        filter = [term]
        if "access" in ask[1]:
            filter.append({"term": {"authorization.access": ask[1]["access"]}})
        if "user" in ask[1]:
            filter.append({"term": {"authorization.owner": ask[1]["user"]}})
        assert query == {"bool": {"filter": filter}}

    @pytest.mark.parametrize(
        "ask",
        [
            ({}, {"access": "public"}),
            ({"access": "public"}, {"access": "public"}),
            ({"user": USER_ID}, {"user": USER_ID, "access": "public"}),
            (
                {"user": USER_ID, "access": "public"},
                {"user": USER_ID, "access": "public"},
            ),
        ],
    )
    def test_noauth(self, elasticbase, server_config, current_user_none, ask):
        """
        Test the query builder when we have an authorized user.

        NOTES:

        2) We don't test {"access": "private"} here: That raises the
           AssemblyError exception, and is tested in a separate test case.
        """
        term = {"term": {"icecream": "ginger"}}
        query = elasticbase._get_user_query(ask[0], [term])
        filter = [term]
        if "access" in ask[1]:
            filter.append({"term": {"authorization.access": ask[1]["access"]}})
        if "user" in ask[1]:
            filter.append({"term": {"authorization.owner": ask[1]["user"]}})
        assert query == {"bool": {"filter": filter}}

    def test_auth_access_private(self, elasticbase, server_config, current_user_drb):
        """
        Test the query builder when "private" access is specified by an
        authenticated client, for another user. This is an "impossible" case as
        authorization checks will stop the request and return UNAUTHORIZED
        before we get here. We cover the code path anyway, looking for the
        AssemblyError exception.
        """
        with pytest.raises(AssemblyError) as excinfo:
            elasticbase._get_user_query(
                {"access": "private", "user": USER_ID},
                [{"term": {"icecream": "vanilla"}}],
            )
        assert excinfo.type == AssemblyError
        assert excinfo.value.status == HTTPStatus.INTERNAL_SERVER_ERROR
        assert (
            str(excinfo.value)
            == "Assembly error returning 500: \"Internal error: Requestor 'drb' can't query private data\""
        )

    @pytest.mark.parametrize(
        "ask", [{"access": "private"}, {"user": USER_ID, "access": "private"}]
    )
    def test_noauth_access_private(
        self, elasticbase, server_config, current_user_none, ask
    ):
        """
        Test the query builder when "private" access is specified by an
        unauthenticated client. This is an "impossible" case as authorization
        checks will stop the request and return UNAUTHORIZED before we get
        here. We cover the code path anyway, looking for the AssemblyError
        exception.
        """
        with pytest.raises(AssemblyError) as excinfo:
            elasticbase._get_user_query(ask, [{"term": {"icecream": "vanilla"}}])
        assert excinfo.type == AssemblyError
        assert excinfo.value.status == HTTPStatus.INTERNAL_SERVER_ERROR
        assert (
            str(excinfo.value)
            == 'Assembly error returning 500: "Internal error: Unauthorized requestor can\'t query private data"'
        )

    def test_neither_auth(self, elasticbase, server_config, current_user_drb):
        """
        Test the query builder for {} when the client is authorized with a
        non-admin account. This is the most complicated query, translating to
        matching owner OR public access. (That is, all datasets owned by the
        authorized user plus all public datasets regardless of owner.)
        """
        id = str(current_user_drb.id)
        query: JSON = elasticbase._get_user_query(
            {}, [{"term": {"icecream": "vanilla"}}]
        )
        assert query == {
            "bool": {
                "filter": [
                    {"term": {"icecream": "vanilla"}},
                    {
                        "dis_max": {
                            "queries": [
                                {"term": {"authorization.owner": id}},
                                {"term": {"authorization.access": "public"}},
                            ]
                        }
                    },
                ]
            }
        }
