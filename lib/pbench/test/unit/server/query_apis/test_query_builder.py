from http import HTTPStatus
import pytest

from pbench.server.api.resources import Schema
from pbench.server.api.auth import Auth
from pbench.server.api.resources.query_apis import AssemblyError, ElasticBase, JSON
from pbench.server.database.models.users import User


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

    def test_user_and_access(self, elasticbase, server_config, current_user_drb):
        """
        Test the query builder when both user and access are specified. This is
        a simple path; the builder assumes that there is an authenticated user
        and that user has access to the specified dataset owner. We just build
        both terms into the query.
        """
        id = str(current_user_drb.id)
        query: JSON = elasticbase._get_user_query(
            {"user": id, "access": "public"}, [{"term": {"icecream": "vanilla"}}]
        )
        assert query == {
            "bool": {
                "filter": [
                    {"term": {"icecream": "vanilla"}},
                    {"term": {"authorization.owner": id}},
                    {"term": {"authorization.access": "public"}},
                ]
            }
        }

    def test_user(self, elasticbase, server_config, current_user_drb):
        """
        Test the query builder when only a user is specified. We expect the
        query builder to add the user term. Note that in the real server we
        can reach the builder only if there is an authenticated user which
        can access datasets owned by the specified user, so it simply builds
        the query.
        """
        id = str(current_user_drb.id)
        query: JSON = elasticbase._get_user_query(
            {"user": id}, [{"term": {"icecream": "chocolate"}}]
        )
        assert query == {
            "bool": {
                "filter": [
                    {"term": {"icecream": "chocolate"}},
                    {"term": {"authorization.owner": id}},
                ]
            }
        }

    def test_user_admin(self, elasticbase, server_config, current_user_admin):
        """
        Test the query builder when only a user is specified with administrator
        authentication. We expect the query builder to add the user term.

        This is the same code path as `test_user`, above, and doesn't add any
        coverage, but "feels" distinct.
        """
        # Invent a user ID that's different from the generated admin user's ID;
        # the value doesn't matter for this test.
        id = str(current_user_admin.id + 1)
        query: JSON = elasticbase._get_user_query(
            {"user": id}, [{"term": {"icecream": "keylime"}}]
        )
        assert query == {
            "bool": {
                "filter": [
                    {"term": {"icecream": "keylime"}},
                    {"term": {"authorization.owner": id}},
                ]
            }
        }

    def test_access_noauth_private(self, elasticbase, server_config, current_user_none):
        """
        Test the query builder when "private" access is specified by an
        unauthenticated client. This is an "impossible" case as authorization
        checks will stop the request and return UNAUTHORIZED before we get
        here. We cover the code path anyway, looking for the AssemblyError
        exception.
        """
        with pytest.raises(AssemblyError) as excinfo:
            elasticbase._get_user_query(
                {"access": "private"}, [{"term": {"icecream": "vanilla"}}]
            )
        assert excinfo.type == AssemblyError
        assert excinfo.value.status == HTTPStatus.INTERNAL_SERVER_ERROR
        assert (
            str(excinfo.value)
            == 'Assembly error returning 500: "Internal error: can\'t generate query for user None, access private"'
        )

    def test_access_noauth_public(self, elasticbase, server_config, current_user_none):
        """
        Test the query builder when "public" access is specified by an
        unauthenticated client. This should build a query that will return all
        public datasets.
        """
        query: JSON = elasticbase._get_user_query(
            {"access": "public"}, [{"term": {"icecream": "vanilla"}}]
        )
        assert query == {
            "bool": {
                "filter": [
                    {"term": {"icecream": "vanilla"}},
                    {"term": {"authorization.access": "public"}},
                ]
            }
        }

    def test_access_user_private(self, elasticbase, server_config, current_user_drb):
        """
        Test the query builder when "private" access is specified by an
        authenticated non-admin client. This should build a query that will
        return all private datasets owned by the authenticated user.
        """
        id = str(current_user_drb.id)
        query: JSON = elasticbase._get_user_query(
            {"access": "private"}, [{"term": {"icecream": "vanilla"}}]
        )
        assert query == {
            "bool": {
                "filter": [
                    {"term": {"icecream": "vanilla"}},
                    {"term": {"authorization.access": "private"}},
                    {"term": {"authorization.owner": id}},
                ]
            }
        }

    def test_access_admin_private(self, elasticbase, server_config, current_user_admin):
        """
        Test the query builder when "private" access is specified by an
        authenticated admin client. This should build a query that will
        return all private datasets regardless of user.
        """
        query: JSON = elasticbase._get_user_query(
            {"access": "private"}, [{"term": {"icecream": "vanilla"}}]
        )
        assert query == {
            "bool": {
                "filter": [
                    {"term": {"icecream": "vanilla"}},
                    {"term": {"authorization.access": "private"}},
                ]
            }
        }

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

    def test_neither_noauth(self, elasticbase, server_config, current_user_none):
        """
        Test the query builder for {} when the client is not authorized. This
        should be treated the same as {"access": "public"} as only public
        datasets are accessible in this case.
        """
        query: JSON = elasticbase._get_user_query(
            {}, [{"term": {"icecream": "vanilla"}}]
        )
        assert query == {
            "bool": {
                "filter": [
                    {"term": {"icecream": "vanilla"}},
                    {"term": {"authorization.access": "public"}},
                ]
            }
        }

    def test_neither_admin(self, elasticbase, server_config, current_user_admin):
        """
        Test the query builder for {} when the client is authenticated as an
        ADMIN user. This is actually the simplest query, because all datasets
        are accessible and only the subclass primary query terms are relevant.
        """
        query: JSON = elasticbase._get_user_query(
            {}, [{"term": {"icecream": "vanilla"}}]
        )
        assert query == {"bool": {"filter": [{"term": {"icecream": "vanilla"}}]}}
