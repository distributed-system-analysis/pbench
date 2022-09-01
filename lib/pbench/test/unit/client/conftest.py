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
            "api": {"login": f"{pbench.url}/api/v1/login"},
            "uri": {},
        },
    )
    pbench.connect({"accept": "application/json"})
    return pbench
