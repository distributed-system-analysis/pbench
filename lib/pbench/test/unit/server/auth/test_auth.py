import configparser
from dataclasses import dataclass
from http import HTTPStatus
from typing import Dict, Optional, Union

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from flask import current_app, Flask
import jwt
import pytest
import requests
from requests.structures import CaseInsensitiveDict

from pbench.server import JSON
import pbench.server.auth
from pbench.server.auth import (
    Connection,
    InternalUser,
    OpenIDCAuthenticationError,
    OpenIDClient,
    OpenIDClientError,
    OpenIDTokenInvalid,
)
import pbench.server.auth.auth as Auth
from pbench.server.database.models.users import User
from pbench.test.unit.server import DRB_USER_ID
from pbench.test.unit.server.conftest import jwt_secret


def test_openid_client_error_exc():
    """Verify behavior of OpenIDClientError exception class"""
    obj = OpenIDClientError(HTTPStatus.CONFLICT)
    assert str(obj) == "Conflict"
    assert repr(obj) == "OIDC error 409 : Conflict"

    obj = OpenIDClientError(HTTPStatus.OK, "my message")
    assert str(obj) == "my message"
    assert repr(obj) == "OIDC error 200 : my message"


class TestConnection:
    """Verify the helper connection class used by the OpenIDClient class."""

    @pytest.fixture
    def fake_method(self, monkeypatch):
        args = {}

        def fake_method(
            the_self, method: str, path: str, data: Dict, **kwargs
        ) -> requests.Response:
            args["method"] = method
            args["path"] = path
            args["data"] = data
            args["kwargs"] = kwargs
            return requests.Response()

        monkeypatch.setattr(Connection, "_method", fake_method)
        return args

    @pytest.fixture
    def conn(self):
        return Connection("https://example.com", None, False)

    def test_under_method(self, monkeypatch):
        """Verify the behavior of Connection._method()

        Args:
            monkeypatch : required to mock out the session object instantiated
                during construction of a Connection object
        """

        class MockResponse:
            """A mocked Response object duck-typed to provide the 'status_code'
            field and the 'ok' property

            The 'ok' property is set based on the provided 'status_code' value.
            """

            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs
                params = kwargs["params"]
                self.status_code = (
                    200 if "status_code" not in params else params["status_code"]
                )
                self.ok = True if self.status_code < 400 else False

        class MockSession:
            """A mocked Session object duck-typed to provide the 'request'
            method
            """

            def request(self, *args, **kwargs):
                """A mocked version of a Session object's 'request' method

                Raises:
                    requests.exceptions.Timeout : when the 2nd argument ends
                        with "timeout"
                    requests.exceptions.ConnectionError : when the 2nd argument
                        ends with "connerr"
                    Exception : when the 2nd argument ends with "exc"
                """
                if args[1].endswith("timeout"):
                    raise requests.exceptions.Timeout()
                elif args[1].endswith("connerr"):
                    raise requests.exceptions.ConnectionError()
                elif args[1].endswith("exc"):
                    raise Exception("Some exception, huh?")
                return MockResponse(*args, **kwargs)

        # We use one Connection object to verify all the behaviors below.
        monkeypatch.setattr(requests, "Session", MockSession)
        conn = Connection("https://example.com", {"header0": "zero"}, False)

        # By default, everything works normally.
        response = conn._method(
            "HEAD",
            "/this/that",
            None,
            headers={"header1": "one"},
            this="that",
            that="this",
        )
        assert response.ok
        assert response.args[0] == "HEAD"
        assert response.args[1] == "https://example.com/this/that"
        assert response.kwargs["params"] == {"this": "that", "that": "this"}
        assert response.kwargs["data"] is None
        assert response.kwargs["headers"] == {"header0": "zero", "header1": "one"}
        assert response.kwargs["verify"] is False

        # Verify that any non-"OK" status code raises the proper exception.
        with pytest.raises(OpenIDCAuthenticationError) as e:
            conn._method("HEAD", "/this/that", None, status_code=409)
        assert e.value.http_status == 409

        # A "Timeout" exception should result in "bad gateway".
        with pytest.raises(OpenIDClientError) as e:
            conn._method("HEAD", "/this/that/timeout", None)
        assert e.value.http_status == HTTPStatus.BAD_GATEWAY

        # A "ConnectionError" exception should result in "bad gateway" as well.
        with pytest.raises(OpenIDClientError) as e:
            conn._method("HEAD", "/this/that/connerr", None)
        assert e.value.http_status == HTTPStatus.BAD_GATEWAY

        # Any other 'Exception" should result in an "internal server error".
        with pytest.raises(OpenIDClientError) as e:
            conn._method("HEAD", "/this/that/exc", None)
        assert e.value.http_status == HTTPStatus.INTERNAL_SERVER_ERROR

    def test_get(self, fake_method, conn):
        """Verify the Connection.get() method properly invokes ._method()

        Args (fixtures):
            fake_method : mocks out ._method() and provides the "args" value so
                that how ._method() is invoked can be checked
            conn : an existing Connection object to use for testing
        """
        args = fake_method
        response = conn.get("foo/bar", this="that", then="now")
        assert response is not None
        assert args["method"] == "GET"
        assert args["path"] == "foo/bar"
        assert args["data"] is None
        assert args["kwargs"] == {"headers": None, "this": "that", "then": "now"}

    def test_post(self, fake_method, conn):
        """Verify the Connection.post() method properly invokes ._method()

        Args (fixtures):
            fake_method : mocks out ._method() and provides the "args" value so
                that how ._method() is invoked can be checked
            conn : an existing Connection object to use for testing
        """
        args = fake_method
        response = conn.post("foo/bar", {"one": "two", "three": "four"}, five="six")
        assert response is not None
        assert args["method"] == "POST"
        assert args["path"] == "foo/bar"
        assert args["data"] == {"one": "two", "three": "four"}
        assert args["kwargs"] == {"headers": None, "five": "six"}


class TestInternalUser:
    """Verify the behavior of the InternalUser class"""

    def test_str(self):
        user = InternalUser(id="X", username="Y", email="Z")
        assert str(user) == "User, id: X, username: Y"

    def test_is_admin(self):
        user = InternalUser(id="X", username="Y", email="Z")
        assert not user.is_admin()
        user = InternalUser(id="X", username="Y", email="Z", roles=["ADMIN"])
        assert user.is_admin()

    def test_create_missing_sub(self):
        with pytest.raises(KeyError):
            InternalUser.create("us", {})

    def test_create_just_sub(self):
        user = InternalUser.create("us", {"sub": "them"})
        assert user.id == "them"
        assert user.username is None
        assert user.email is None
        assert user.first_name is None
        assert user.last_name is None
        assert user.roles == []

    def test_create_full(self):
        user = InternalUser.create(
            "us",
            {
                "sub": "them",
                "preferred_username": "userA",
                "email": "userA@hostB.net",
                "given_name": "Agiven",
                "family_name": "Family",
            },
        )
        assert user.id == "them"
        assert user.username == "userA"
        assert user.email == "userA@hostB.net"
        assert user.first_name == "Agiven"
        assert user.last_name == "Family"
        assert user.roles == []

    def test_create_w_roles(self):
        # Verify not in audience list
        # FIXME - this is weird as coded, why would we get a payload where so
        # other audience is listed?
        user = InternalUser.create(
            "us",
            {"sub": "them", "resource_access": {"not-us": {}}},
        )
        assert user.id == "them"
        assert user.username is None
        assert user.email is None
        assert user.first_name is None
        assert user.last_name is None
        assert user.roles == []

        user = InternalUser.create(
            "us",
            {"sub": "them", "resource_access": {"us": {"roles": ["roleA", "roleB"]}}},
        )
        assert user.id == "them"
        assert user.username is None
        assert user.email is None
        assert user.first_name is None
        assert user.last_name is None
        assert user.roles == ["roleA", "roleB"]


@pytest.fixture(scope="session")
def rsa_keys() -> Dict[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_public_key = (
        private_key.public_key()
        .public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    public_key_l = pem_public_key.split("\n")[1:-1]
    public_key = ""
    for el in public_key_l:
        if el.endswith("-----END PUBLIC KEY-----"):
            el = el[:-24]
        public_key += el
    return {
        "private_key": private_key,
        "public_key": public_key,
        "pem_public_key": pem_public_key,
    }


def gen_rsa_token(
    audience: str, private_key: str, exp: str = "99999999999"
) -> Dict[str, str]:
    payload = {"iat": 1659476706, "exp": exp, "sub": "12345", "aud": audience}

    # Get jwt key
    return jwt.encode(payload, key=private_key, algorithm="RS256"), payload


def mock_connection(
    monkeypatch, client_id: str, public_key: Optional[str] = None
) -> configparser.ConfigParser:
    """Create a mocked Connection object whose behavior is driven off of
    the realm name and / or client ID.

    Args:
        client_id : A client ID used to influence the behavior of the mocked
            Connection object
        public_key : [optional] Public key to use

    Returns:
        A configparser.ConfigParser object for use constructing an
            OpenIDClient object
    """
    server_url = "https://example.com"
    realm_name = "camelot"
    secret = "shhh"
    config = configparser.ConfigParser()
    config["openid-connect"] = {
        "server_url": server_url,
        "client": client_id,
        "realm": realm_name,
        "secret": secret,
    }
    public_key = "abcdefg" if public_key is None else public_key

    class MockResponse:
        """A mocked requests.Response object which just provides a json()
        method.
        """

        def __init__(self, json: str):
            self._json = json

        def json(self):
            return self._json

    class MockConnection:
        """A mocked Connection to allow behavioral control for testing

        The client configuration parameter value is the vehicle for
        directing various good or bad behaviors as required.
        """

        def __init__(
            self,
            server_url: str,
            headers: Optional[Dict[str, str]] = None,
            verify: bool = True,
        ):
            self.server_url = server_url
            self.headers = CaseInsensitiveDict({} if headers is None else headers)
            self.verify = verify

        def get(self, path: str, **kwargs) -> MockResponse:
            if path.endswith(f"realms/{realm_name}"):
                json_d = {"public_key": public_key}
            elif path.endswith(f"realms/{realm_name}/.well-known/openid-configuration"):
                json_d = {
                    "userinfo_endpoint": f"{self.server_url}/userinfo",
                    "introspection_endpoint": f"{self.server_url}/introspection",
                }
                if client_id == "us-missing-userinfo-ep":
                    del json_d["userinfo_endpoint"]
                elif client_id == "us-missing-introspection-ep":
                    del json_d["introspection_endpoint"]
                elif client_id == "us-empty-tokeninfo-ep":
                    json_d["introspection_endpoint"] = ""
            elif path.endswith("userinfo"):
                json_d = {"path": path, "kwargs": kwargs}
            else:
                raise Exception(f"MockConnection: unrecognized .get(path={path})")
            return MockResponse(json_d)

        def post(self, path: str, data: Dict, **kwargs) -> MockResponse:
            if path.endswith("/introspection"):
                if client_id == "us-raise-exc":
                    raise OpenIDClientError(400, "Introspection failed")
                cid = "other-client" if client_id == "us-other-aud" else client_id
                json_d = {"aud": [cid], "data": data}
                if client_id == "us-token-payload":
                    json_d["sub"] = "67890"
            else:
                raise Exception(f"MockConnection: unrecognized .post(path={path})")
            return MockResponse(json_d)

    monkeypatch.setattr(pbench.server.auth, "Connection", MockConnection)
    return config


class TestOpenIDClient:
    """Verify the OpenIDClient class."""

    def test_construct_oidc_client_fail(self):
        """Verfiy .construct_oidc_client() failure mode"""

        # Start with an empty configuration, no openid-connect section
        config = configparser.ConfigParser()
        with pytest.raises(OpenIDClient.NotConfigured):
            OpenIDClient.construct_oidc_client(config)

        # Missing "server_url"
        section = {}
        config["openid-connect"] = section
        with pytest.raises(OpenIDClient.NotConfigured):
            OpenIDClient.construct_oidc_client(config)

        section["server_url"] = "https://example.com"
        # Missing client
        with pytest.raises(OpenIDClient.NotConfigured):
            OpenIDClient.construct_oidc_client(config)
        section["client"] = "us"
        # Missing realm
        with pytest.raises(OpenIDClient.NotConfigured):
            OpenIDClient.construct_oidc_client(config)
        section["realm"] = "camelot"
        # Missing secret
        with pytest.raises(OpenIDClient.NotConfigured):
            OpenIDClient.construct_oidc_client(config)

    def test_construct_oidc_client_succ(self, monkeypatch):
        """Verify .construct_oidc_client() success mode"""
        client_id = "us"
        public_key = "hijklmn"
        config = mock_connection(monkeypatch, client_id, public_key)
        server_url = config["openid-connect"]["server_url"]
        realm_name = config["openid-connect"]["realm"]
        secret = config["openid-connect"]["secret"]

        oidc_client = OpenIDClient.construct_oidc_client(config)

        assert repr(oidc_client) == (
            f"OpenIDClient(server_url={server_url}, "
            f"client_id={client_id}, realm_name={realm_name}, "
            "headers={})"
        )
        assert oidc_client._client_secret_key == secret
        assert (
            oidc_client._pem_public_key
            == f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----\n"
        )
        assert oidc_client._userinfo_endpoint.endswith("/userinfo")
        assert oidc_client._tokeninfo_endpoint.endswith("/introspection")

    def test_construct_oidc_client_fail_ep(self, monkeypatch):
        """Verify .construct_oidc_client() failure mode where OpenIDClientError
        is raised
        """
        # First failure should be caused by missing "userinfo" endpoint.
        client_id = "us-missing-userinfo-ep"
        config = mock_connection(monkeypatch, client_id)
        with pytest.raises(OpenIDClientError):
            OpenIDClient.construct_oidc_client(config)

        # Second failure should be caused by missing "introspection" endpoint.
        client_id = "us-missing-introspection-ep"
        config = mock_connection(monkeypatch, client_id)
        with pytest.raises(OpenIDClientError):
            OpenIDClient.construct_oidc_client(config)

    def test_token_introspect_online_no_ep(self, monkeypatch):
        """Verify .token_introspect_online() with empty token information end
        point
        """
        client_id = "us-empty-tokeninfo-ep"
        public_key = "opqrstu"
        config = mock_connection(monkeypatch, client_id, public_key)
        oidc_client = OpenIDClient.construct_oidc_client(config)
        json_d = oidc_client.token_introspect_online("my-token")
        assert json_d is None

    def test_token_introspect_online_not_aud(self, monkeypatch):
        """Verify .token_introspect_online() with different audience."""
        client_id = "us-other-aud"
        public_key = "vwxyz01"
        config = mock_connection(monkeypatch, client_id, public_key)
        oidc_client = OpenIDClient.construct_oidc_client(config)
        json_d = oidc_client.token_introspect_online("my-token")
        assert json_d is None, f"{json_d!r}"

    def test_token_introspect_online_succ(self, monkeypatch):
        """Verify .token_introspect_online() with different audience."""
        client_id = "us"
        public_key = "2345678"
        config = mock_connection(monkeypatch, client_id, public_key)
        secret = config["openid-connect"]["secret"]
        oidc_client = OpenIDClient.construct_oidc_client(config)
        json_d = oidc_client.token_introspect_online("my-token")
        assert json_d["aud"] == [client_id]
        assert json_d["data"] == {
            "client_id": client_id,
            "client_secret": secret,
            "token": "my-token",
        }, f"{json_d!r}"

    def test_token_introspect_offline_succ(self, monkeypatch, rsa_keys):
        """Verify .token_introspect_offline() success path"""
        client_id = "us"
        token, expected_payload = gen_rsa_token(client_id, rsa_keys["private_key"])

        # Mock the Connection object and generate an OpenIDClient object.
        config = mock_connection(
            monkeypatch, client_id, public_key=rsa_keys["public_key"]
        )
        oidc_client = OpenIDClient.construct_oidc_client(config)

        # We don't strictly need to verify these two fields, but it is helpful
        # to ensure they are correct before performing the offline
        # introspection.
        assert oidc_client.client_id == "us"
        assert (
            oidc_client._pem_public_key == rsa_keys["pem_public_key"]
        ), "got={}\nexpected={}\npublic_key={}".format(
            oidc_client._pem_public_key,
            rsa_keys["pem_public_key"],
            rsa_keys["public_key"],
        )

        # This is the target test case.
        response = oidc_client.token_introspect_offline(token)
        assert response == expected_payload

    def test_token_introspect_offline_exp(self, monkeypatch, rsa_keys):
        """Verify .token_introspect_offline() failure via expiration"""
        client_id = "us"
        token, expected_payload = gen_rsa_token(
            client_id, rsa_keys["private_key"], exp=42
        )

        # Mock the Connection object and generate an OpenIDClient object.
        config = mock_connection(
            monkeypatch, client_id, public_key=rsa_keys["public_key"]
        )
        oidc_client = OpenIDClient.construct_oidc_client(config)

        with pytest.raises(OpenIDTokenInvalid) as exc:
            oidc_client.token_introspect_offline(token)
        assert (
            str(exc.value.__cause__) == "Signature has expired"
        ), f"{exc.value.__cause__}"

    def test_token_introspect_offline_aud(self, monkeypatch, rsa_keys):
        """Verify .token_introspect_offline() failure via audience error"""
        client_id = "us"
        token, expected_payload = gen_rsa_token(client_id, rsa_keys["private_key"])

        # Mock the Connection object and generate an OpenIDClient object using
        # a different client ID (audience).
        config = mock_connection(monkeypatch, "them", public_key=rsa_keys["public_key"])
        oidc_client = OpenIDClient.construct_oidc_client(config)

        with pytest.raises(OpenIDTokenInvalid) as exc:
            oidc_client.token_introspect_offline(token)
        assert str(exc.value.__cause__) == "Invalid audience", f"{exc.value.__cause__}"

    def test_token_introspect_offline_sig(self, monkeypatch, rsa_keys):
        """Verify .token_introspect_offline() failure via signature error"""
        client_id = "us"
        token, expected_payload = gen_rsa_token(client_id, rsa_keys["private_key"])

        # Mock the Connection object and generate an OpenIDClient object using
        # a different client ID (audience).
        config = mock_connection(
            monkeypatch, client_id, public_key=rsa_keys["public_key"]
        )
        oidc_client = OpenIDClient.construct_oidc_client(config)

        with pytest.raises(OpenIDTokenInvalid) as exc:
            # Make the signature invalid.
            oidc_client.token_introspect_offline(token + "1")
        assert (
            str(exc.value.__cause__) == "Signature verification failed"
        ), f"{exc.value.__cause__}"

    def test_get_userinfo(self, monkeypatch):
        """Verify .get_userinfo() properly invokes Connection.get()"""
        # Mock the Connection object and generate an OpenIDClient object.
        client_id = "us"
        config = mock_connection(monkeypatch, client_id)
        oidc_client = OpenIDClient.construct_oidc_client(config)

        # Ensure .get_userinfo() invokes Connection.get() with the correct
        # parameters.
        token = "the-token"
        json_d = oidc_client.get_userinfo(token)
        assert json_d == {
            "kwargs": {"headers": {"Authorization": "Bearer the-token"}},
            "path": "https://example.com/userinfo",
        }


@dataclass
class MockRequest:
    """A simple way to mock out Flask's `request.headers` dictionary."""

    headers: Dict


class TestAuthModule:
    """Verify the behaviors of the auth (Auth) module

    This class does not verify the setup_app() method itself is it is verified
    in other tests related to the overall Flask application setup.

    It also does not attempt to verify get_current_user_id() and
    encode_auth_token() since they are slated for removal and are covered well
    by other parts of the unit testing for the server code.

    It does, however, verify the verify_auth_internal() method because we need
    it to function properly until the use of an internal user is removed.
    """

    def test_get_auth_token_succ(self, monkeypatch, make_logger):
        """Verify behaviors of fetching the authorization token from HTTP
        headers works properly
        """
        monkeypatch.setattr(
            Auth, "request", MockRequest(headers={"Authorization": "Bearer my-token"})
        )
        token = Auth.get_auth_token()
        assert token == "my-token"

        monkeypatch.setattr(
            Auth,
            "request",
            MockRequest(headers={"Authorization": "bearer my-other-token"}),
        )
        token = Auth.get_auth_token()
        assert token == "my-other-token"

    @pytest.mark.parametrize(
        "headers",
        [{"Authorization": "not-bearer my-token"}, {"Authorization": "no-space"}, {}],
    )
    def test_get_auth_token_fail(self, monkeypatch, make_logger, headers):
        """Verify error handling fetching the authorization token from HTTP
        headers
        """

        class AbortErr(Exception):
            pass

        record = {"code": None, "message": None}

        def record_abort(code: int, message: str = ""):
            record["code"] = code
            raise AbortErr()

        # We only need to set this once for remaining checks.
        monkeypatch.setattr(Auth, "abort", record_abort)

        app = Flask("test-get-auth-token-fail")
        app.logger = make_logger
        with app.app_context():
            monkeypatch.setattr(Auth, "request", MockRequest(headers=headers))
            try:
                Auth.get_auth_token()
            except AbortErr:
                pass
            else:
                pytest.fail("abort() was not called")
            expected_code = (
                HTTPStatus.UNAUTHORIZED
                if "Authorization" in headers
                else HTTPStatus.FORBIDDEN
            )
            assert record["code"] == expected_code

    def test_verify_auth_exc(self, monkeypatch, make_logger):
        def vai_exc(token_auth: str) -> Optional[Union[User, InternalUser]]:
            raise Exception("Some failure")

        monkeypatch.setattr(Auth, "verify_auth_internal", vai_exc)
        app = Flask("test-verify-auth-exc")
        app.logger = make_logger
        with app.app_context():
            user = Auth.verify_auth("my-token")
        assert user is None

    def test_verify_auth_internal(self, make_logger, pbench_drb_token):
        app = Flask("test-verify-auth-internal")
        app.logger = make_logger
        with app.app_context():
            current_app.secret_key = jwt_secret
            user = Auth.verify_auth(pbench_drb_token)
        assert str(user.id) == DRB_USER_ID

    def test_verify_auth_internal_invalid(self, make_logger, pbench_drb_token_invalid):
        app = Flask("test-verify-auth-internal-invalid")
        app.logger = make_logger
        with app.app_context():
            current_app.secret_key = jwt_secret
            user = Auth.verify_auth(pbench_drb_token_invalid)
        assert user is None

    def test_verify_auth_internal_invsig(self, make_logger, pbench_drb_token):
        app = Flask("test-verify-auth-internal-invsig")
        app.logger = make_logger
        with app.app_context():
            current_app.secret_key = jwt_secret
            user = Auth.verify_auth(pbench_drb_token + "1")
        assert user is None

    def test_verify_auth_internal_tokdel_fail(
        self, monkeypatch, make_logger, pbench_drb_token_invalid
    ):
        def delete(*args, **kwargs):
            raise Exception("Delete failed")

        monkeypatch.setattr(Auth.ActiveTokens, "delete", delete)
        app = Flask("test-verify-auth-internal-tokdel-fail")
        app.logger = make_logger
        with app.app_context():
            current_app.secret_key = jwt_secret
            user = Auth.verify_auth(pbench_drb_token_invalid)
        assert user is None

    def test_verify_auth_internal_at_valid_fail(
        self, monkeypatch, make_logger, pbench_drb_token
    ):
        def valid(*args, **kwargs):
            return False

        monkeypatch.setattr(Auth.ActiveTokens, "valid", valid)
        app = Flask("test-verify-auth-internal-at-valid-fail")
        app.logger = make_logger
        with app.app_context():
            current_app.secret_key = jwt_secret
            user = Auth.verify_auth(pbench_drb_token)
        assert user is None

    def test_verify_auth_oidc_offline(self, monkeypatch, rsa_keys, make_logger):
        client_id = "us"
        token, expected_payload = gen_rsa_token(client_id, rsa_keys["private_key"])

        # Mock the Connection object and generate an OpenIDClient object,
        # installing it as Auth module's OIDC client.
        config = mock_connection(
            monkeypatch, client_id, public_key=rsa_keys["public_key"]
        )
        oidc_client = OpenIDClient.construct_oidc_client(config)
        monkeypatch.setattr(Auth, "oidc_client", oidc_client)

        app = Flask("test-verify-auth-oidc-offline")
        app.logger = make_logger
        with app.app_context():
            user = Auth.verify_auth(token)

        assert user.id == "12345"

    def test_verify_auth_oidc_offline_invalid(self, monkeypatch, rsa_keys, make_logger):
        """Verify OIDC token offline verification via Auth.verify_auth() fails
        gracefully with an invalid token
        """
        client_id = "us"
        token, expected_payload = gen_rsa_token(client_id, rsa_keys["private_key"])

        # Mock the Connection object and generate an OpenIDClient object,
        # installing it as Auth module's OIDC client.
        config = mock_connection(
            monkeypatch, client_id, public_key=rsa_keys["public_key"]
        )
        oidc_client = OpenIDClient.construct_oidc_client(config)
        monkeypatch.setattr(Auth, "oidc_client", oidc_client)

        def tio_exc(token: str) -> JSON:
            raise OpenIDTokenInvalid()

        app = Flask("test-verify-auth-oidc-offline-invalid")
        app.logger = make_logger
        with app.app_context():
            monkeypatch.setattr(oidc_client, "token_introspect_offline", tio_exc)
            user = Auth.verify_auth(token)

        assert user is None

    def test_verify_auth_oidc_online(self, monkeypatch, rsa_keys, make_logger):
        """Verify OIDC token online verification works via Auth.verify_auth()"""
        # Use the client ID to direct the MockConnection class to return a
        # token payload.
        client_id = "us-token-payload"
        token, expected_payload = gen_rsa_token(client_id, rsa_keys["private_key"])

        # Mock the Connection object and generate an OpenIDClient object,
        # installing it as Auth module's OIDC client.
        config = mock_connection(
            monkeypatch, client_id, public_key=rsa_keys["public_key"]
        )
        oidc_client = OpenIDClient.construct_oidc_client(config)
        monkeypatch.setattr(Auth, "oidc_client", oidc_client)

        def tio_exc(token: str) -> JSON:
            raise Exception("Token introspection offline failed for some reason")

        app = Flask("test-verify-auth-oidc-online")
        app.logger = make_logger
        with app.app_context():
            monkeypatch.setattr(oidc_client, "token_introspect_offline", tio_exc)
            user = Auth.verify_auth(token)

        assert user.id == "67890"

    def test_verify_auth_oidc_online_fail(self, monkeypatch, rsa_keys, make_logger):
        """Verify OIDC token online verification via Auth.verify_auth() fails
        returning None
        """
        # Use the client ID to direct the online token introspection to raise
        # an OpenIDClientError.
        client_id = "us-raise-exc"
        token, expected_payload = gen_rsa_token(client_id, rsa_keys["private_key"])

        # Mock the Connection object and generate an OpenIDClient object,
        # installing it as Auth module's OIDC client.
        config = mock_connection(
            monkeypatch, client_id, public_key=rsa_keys["public_key"]
        )
        oidc_client = OpenIDClient.construct_oidc_client(config)
        monkeypatch.setattr(Auth, "oidc_client", oidc_client)

        def tio_exc(token: str) -> JSON:
            raise Exception("Token introspection offline failed for some reason")

        app = Flask("test-verify-auth-oidc-online-fail")
        app.logger = make_logger
        with app.app_context():
            monkeypatch.setattr(oidc_client, "token_introspect_offline", tio_exc)
            user = Auth.verify_auth(token)

        assert user is None
