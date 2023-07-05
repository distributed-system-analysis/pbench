from pbench.client import API, PbenchServerClient


class TestAudit:
    def test_get_all(self, server_client: PbenchServerClient, login_admin):
        """
        Verify that we can retrieve the Pbench Server audit log.

        This relies on a "testadmin" user which has been granted ADMIN role
        via the pbench-server.cfg file for functional testing. The audit API
        should succeed without permissions failure, and we'll validate the
        audit fields of the records we see.
        """
        response = server_client.get(API.SERVER_AUDIT, {})
        json = response.json()
        assert (
            response.ok
        ), f"Reading audit log failed {response.status_code},{json['message']}"
        assert isinstance(json, list)
        print(f" ... read {len(json)} audit records")
        for audit in json:
            assert isinstance(audit["id"], int)
            assert audit["name"]
            assert audit["operation"] in ("CREATE", "READ", "UPDATE", "DELETE")
            assert audit["reason"] in (None, "PERMISSION", "INTERNAL", "CONSISTENCY")
            assert "root_id" in audit
            if audit["root_id"]:
                assert isinstance(audit["root_id"], int)
            assert audit["status"] in ("BEGIN", "SUCCESS", "FAILURE", "WARNING")
            assert audit["timestamp"]
            assert audit["attributes"]
            assert audit["object_type"] in (
                "API_KEY",
                "CONFIG",
                "DATASET",
                "NONE",
                "TEMPLATE",
            )
            if audit["object_type"] != "NONE":
                assert audit["object_name"]
                if audit["object_type"] == "DATASET":
                    assert audit["object_id"]
            if audit["user_name"] not in (None, "BACKGROUND"):
                assert audit["user_id"]
