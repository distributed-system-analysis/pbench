import pytest
import responses

from pbench.client import PbenchServerClient


@pytest.fixture()
@responses.activate
def connect():
    """
    Fake a connection to the Pbench Server API.
    """
    pbench = PbenchServerClient("localhost")
    responses.add(
        responses.GET,
        f"{pbench.url}/api/v1/endpoints",
        json={
            "identification": "string",
            "api": {},
            "uri": {},
            "openid": {
                "server": "http://oidc_server",
                "realm": "pbench-server",
                "client": "pbench-client",
            },
        },
    )
    responses.add(
        responses.POST,
        "http://oidc_server/realms/master/protocol/openid-connect/token",
        json={
            "access_token": "admin_token",
        },
    )
    pbench.connect({"accept": "application/json"})
    return pbench
