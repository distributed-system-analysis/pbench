import responses

from pbench.client import PbenchServerClient


class TestConnect:
    def test_construct_host(self):
        pbench = PbenchServerClient("10.1.100.2")
        assert pbench.host == "10.1.100.2"
        assert pbench.scheme == "https"
        assert pbench.session is None
        assert pbench.endpoints is None

    def test_construct_url(self):
        pbench = PbenchServerClient("https://10.1.100.2")
        assert pbench.host == "https://10.1.100.2"
        assert pbench.scheme == "https"
        assert pbench.session is None
        assert pbench.endpoints is None

    @responses.activate
    def test_connect(self):
        pbench = PbenchServerClient("10.1.100.2")
        url = f"{pbench.url}/api/v1/endpoints"
        openid_dict = {"server": "https://oidc_server", "client": "pbench_client"}

        with responses.RequestsMock() as rsp:
            rsp.add(
                responses.GET,
                url,
                json={
                    "identification": "string",
                    "uri": {},
                    "openid": openid_dict,
                },
            )
            pbench.connect({"accept": "application/json"})
            assert len(rsp.calls) == 1
            assert rsp.calls[0].request.url == url
            assert rsp.calls[0].response.status_code == 200

        # Check standard requests headers. The requests package uses a
        # case-insensitive dictionary for headers, which retains the original
        # case but provides case-insensitive lookups.
        headers = pbench.session.headers
        assert "Accept-Encoding" in headers
        assert "Connection" in headers
        assert "user-agent" in headers
        assert "accept" in headers  # Our header was added
        assert "AcCePt" in headers  # It's case insensitive
        assert headers["ACCEPT"] == "application/json"

        # Check that the fake endpoints we returned are captured
        endpoints = pbench.endpoints
        assert endpoints
        assert endpoints["identification"] == "string"
        assert endpoints["uri"] == {}
        assert endpoints["openid"] == openid_dict
