from pbench.server.api.resources import Schema
import pytest
from pbench.server.api.auth import Auth
from pbench.server.api.resources.query_apis import ElasticBase, JSON, NoSelectedDatasets
from pbench.server.database.models.users import User


class TestQueryBuilder:
    @pytest.fixture()
    def elasticbase(self, client):
        return ElasticBase(client.config, client.logger, Schema())

    @pytest.fixture()
    def current_user_drb(self, monkeypatch):
        class FakeHTTPTokenAuth:
            def current_user(self) -> User:
                return User(
                    email="email@example.com",
                    id=3,
                    username="drb",
                    first_name="Test",
                    last_name="Account",
                )

        with monkeypatch.context() as m:
            m.setattr(Auth, "token_auth", FakeHTTPTokenAuth())
            yield

    @pytest.fixture()
    def current_user_none(self, monkeypatch):
        class FakeHTTPTokenAuth:
            def current_user(self) -> User:
                return None

        with monkeypatch.context() as m:
            m.setattr(Auth, "token_auth", FakeHTTPTokenAuth())
            yield

    @pytest.fixture()
    def current_user_admin(self, monkeypatch):
        class FakeHTTPTokenAuth:
            def current_user(self) -> User:
                return User(
                    email="email@example.com",
                    id=6,
                    username="admin",
                    first_name="Test",
                    last_name="Admin",
                    role="admin",
                )

        with monkeypatch.context() as m:
            m.setattr(Auth, "token_auth", FakeHTTPTokenAuth())
            yield

    def test_user_and_access(
        self, elasticbase, server_config, current_user_drb, user_ok
    ):
        """
        Test the query builder when both user and access are specified. This is
        a simple path; the builder assumes that there is an authenticated user
        and that user has access to the specified dataset owner. We just build
        both terms into the query.
        """
        query: JSON = elasticbase._get_user_query(
            {"user": "drb", "access": "public"}, [{"term": {"icecream": "vanilla"}}]
        )
        assert query == {
            "bool": {
                "filter": [
                    {"term": {"icecream": "vanilla"}},
                    {"term": {"authorization.access": "public"}},
                    {"term": {"authorization.owner": "drb"}},
                ]
            }
        }

    def test_user(self, elasticbase, server_config, current_user_drb, user_ok):
        """
        Test the query builder when only a user is specified. We expect the
        query builder to add the user term. Note that in the real server we
        can reach the builder only if there is an authenticated user which
        can access datasets owned by the specified user, so it simply builds
        the query.
        """
        query: JSON = elasticbase._get_user_query(
            {"user": "drb"}, [{"term": {"icecream": "vanilla"}}]
        )
        assert query == {
            "bool": {
                "filter": [
                    {"term": {"icecream": "vanilla"}},
                    {"term": {"authorization.owner": "drb"}},
                ]
            }
        }

    def test_access_noauth_private(
        self, elasticbase, server_config, current_user_none, user_ok
    ):
        """
        Test the query builder when "private" access is specified by an
        unauthenticated client. This is expected to throw an exception, which
        will be treated as if Elasticsearch returned no hits.
        """
        with pytest.raises(NoSelectedDatasets) as excinfo:
            elasticbase._get_user_query(
                {"access": "private"}, [{"term": {"icecream": "vanilla"}}]
            )
        assert excinfo.type == NoSelectedDatasets
        assert excinfo.value.user is None
        assert excinfo.value.access == "private"
        assert (
            str(excinfo.value)
            == "Query from unauthorized client for access 'private' cannot produce results"
        )

    def test_access_noauth_public(
        self, elasticbase, server_config, current_user_none, user_ok
    ):
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

    def test_access_user_private(
        self, elasticbase, server_config, current_user_drb, user_ok
    ):
        """
        Test the query builder when "private" access is specified by an
        authenticated non-admin client. This should build a query that will
        return all private datasets owned by the authenticated user.
        """
        query: JSON = elasticbase._get_user_query(
            {"access": "private"}, [{"term": {"icecream": "vanilla"}}]
        )
        assert query == {
            "bool": {
                "filter": [
                    {"term": {"icecream": "vanilla"}},
                    {"term": {"authorization.access": "private"}},
                    {"term": {"authorization.owner": "3"}},
                ]
            }
        }

    def test_access_admin_private(
        self, elasticbase, server_config, current_user_admin, user_ok
    ):
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

    def test_neither_auth(self, elasticbase, server_config, current_user_drb, user_ok):
        """
        Test the query builder for {} when the client is authorized with a
        non-admin account. This is the most complicated query, translating to
        matching owner OR public access. (That is, all datasets owned by the
        authorized user plus all public datasets regardless of owner.)
        """
        query: JSON = elasticbase._get_user_query(
            {}, [{"term": {"icecream": "vanilla"}}]
        )
        assert query == {
            "constant_score": {
                "filter": {
                    "bool": {
                        "must": [
                            {"term": {"icecream": "vanilla"}},
                            {
                                "bool": {
                                    "should": [
                                        {"term": {"authorization.owner": "3"}},
                                        {"term": {"authorization.access": "public"}},
                                    ]
                                }
                            },
                        ]
                    }
                }
            }
        }

    def test_neither_noauth(
        self, elasticbase, server_config, current_user_none, user_ok
    ):
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

    def test_neither_admin(
        self, elasticbase, server_config, current_user_admin, user_ok
    ):
        """
        Test the query builder for {} when the client is authenticated as an
        ADMIN user. This is actually the simplest query, because all datasets
        are accessible and only the subclass primary query terms are relevant.
        """
        query: JSON = elasticbase._get_user_query(
            {}, [{"term": {"icecream": "vanilla"}}]
        )
        assert query == {"bool": {"filter": [{"term": {"icecream": "vanilla"}}]}}
