import configparser
from dataclasses import dataclass
from http import HTTPStatus
from typing import Dict, Optional, Tuple, Union

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
        with pytest.raises(OpenIDClientError) as e:
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
        # FIXME - this is weird as coded, why would we get a payload where no
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
def rsa_keys() -> Dict[str, Union[rsa.RSAPrivateKey, str]]:
    """Fixture for generating an RSA public / private key pair.

    Returns:
        A dictionary containing the RSAPrivateKey object, the PEM encoded public
        key string without the BEGIN/END bookends (mimicing what is returned by
        an OpenID Connect broker), and the PEM encoded public key string with
        the BEGIN/END bookends
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_public_key = (
        private_key.public_key()
        .public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    # Strip "-----BEGIN..." and "-----END...", and the empty element resulting
    # from the trailing newline character.
    public_key_l = pem_public_key.split("\n")[1:-2]
    public_key = "".join(public_key_l)
    return {
        "private_key": private_key,
        "public_key": public_key,
        "pem_public_key": pem_public_key,
    }


def gen_rsa_token(
    audience: str, private_key: str, exp: str = "99999999999"
) -> Tuple[str, Dict[str, str]]:
    """Helper function for generating an RSA token using the given private key.

    Args:
        audience : The audience value to used in the encoded 'aud' payload field
        private_key : The private key to use for encoding
        exp : Optional expiration Epoch time stamp to use, defaults to Wednesday
            November 16th, 5138 at 9:47:39 AM UTC
    """
    payload = {"iat": 1659476706, "exp": exp, "sub": "12345", "aud": audience}
    return jwt.encode(payload, key=private_key, algorithm="RS256"), payload


def mock_connection(
    monkeypatch, client_id: str, public_key: Optional[str] = None
) -> configparser.ConfigParser:
    """Create a mocked Connection object whose behavior is driven off of
    the realm name and / or client ID.

    Args:
        client_id : A client ID used to influence the behavior of the mocked
            Connection object
        public_key : Optional public key to use

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
            else:
                raise Exception(f"MockConnection: unrecognized .get(path={path})")
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

    def test_token_introspect_succ(self, monkeypatch, rsa_keys):
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
        response = oidc_client.token_introspect(token)
        assert response == expected_payload

    def test_token_introspect_exp(self, monkeypatch, rsa_keys):
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
            oidc_client.token_introspect(token)
        assert (
            str(exc.value.__cause__) == "Signature has expired"
        ), f"{exc.value.__cause__}"

    def test_token_introspect_aud(self, monkeypatch, rsa_keys):
        """Verify .token_introspect_offline() failure via audience error"""
        client_id = "us"
        token, expected_payload = gen_rsa_token(client_id, rsa_keys["private_key"])

        # Mock the Connection object and generate an OpenIDClient object using
        # a different client ID (audience).
        config = mock_connection(monkeypatch, "them", public_key=rsa_keys["public_key"])
        oidc_client = OpenIDClient.construct_oidc_client(config)

        with pytest.raises(OpenIDTokenInvalid) as exc:
            oidc_client.token_introspect(token)
        assert str(exc.value.__cause__) == "Invalid audience", f"{exc.value.__cause__}"

    def test_token_introspect_sig(self, monkeypatch, rsa_keys):
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
            oidc_client.token_introspect(token + "1")
        assert (
            str(exc.value.__cause__) == "Signature verification failed"
        ), f"{exc.value.__cause__}"


@dataclass
class MockRequest:
    """A simple way to mock out Flask's `request.headers` dictionary."""

    headers: Dict


class TestAuthModule:
    """Verify the behaviors of the auth (Auth) module

    This class does not verify the setup_app() method itself as it is verified
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
        """Verify exception handling originating from verify_auth_internal"""

        def vai_exc(token_auth: str) -> Optional[Union[User, InternalUser]]:
            raise Exception("Some failure")

        monkeypatch.setattr(Auth, "verify_auth_internal", vai_exc)
        app = Flask("test-verify-auth-exc")
        app.logger = make_logger
        with app.app_context():
            user = Auth.verify_auth("my-token")
        assert user is None

    def test_verify_auth_internal(self, make_logger, pbench_drb_token):
        """Verify success path of verify_auth_internal"""
        app = Flask("test-verify-auth-internal")
        app.logger = make_logger
        with app.app_context():
            current_app.secret_key = jwt_secret
            user = Auth.verify_auth(pbench_drb_token)
        assert str(user.id) == DRB_USER_ID

    def test_verify_auth_internal_invalid(self, make_logger, pbench_drb_token_invalid):
        """Verify handling of an invalid (expired) token in verify_auth_internal"""
        app = Flask("test-verify-auth-internal-invalid")
        app.logger = make_logger
        with app.app_context():
            current_app.secret_key = jwt_secret
            user = Auth.verify_auth(pbench_drb_token_invalid)
        assert user is None

    def test_verify_auth_internal_invsig(self, make_logger, pbench_drb_token):
        """Verify handling of a token with an invalid signature"""
        app = Flask("test-verify-auth-internal-invsig")
        app.logger = make_logger
        with app.app_context():
            current_app.secret_key = jwt_secret
            user = Auth.verify_auth(pbench_drb_token + "1")
        assert user is None

    def test_verify_auth_internal_tokdel_fail(
        self, monkeypatch, make_logger, pbench_drb_token_invalid
    ):
        """Verify behavior when token deletion fails"""

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
        """Verify behavior when a token is not in the database"""

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
        """Verify OIDC token offline verification success path"""
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
            monkeypatch.setattr(oidc_client, "token_introspect", tio_exc)
            user = Auth.verify_auth(token)

        assert user is None
