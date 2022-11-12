from pathlib import Path
import time

from pbench.client import PbenchServerClient

TARBALL_DIR = Path("lib/pbench/test/functional/server/tarballs")


class TestPut:
    tarballs: list[Path] = []

    def test_upload_all(self, server_client: PbenchServerClient, login_user):
        """Upload each of the pregenerated tarballs, and perform some basic
        sanity checks on the resulting server state.
        """

        for t in TARBALL_DIR.glob("*.tar.xz"):
            self.tarballs.append(t)
            response = server_client.upload(t)
            assert response.ok
        datasets = server_client.get_list(
            metadata=["server.tarball-path", "server.status"]
        )
        found = sorted(d.name for d in datasets)
        expected = sorted(t.name[:-7] for t in self.tarballs)
        assert found == expected
        for dataset in datasets:
            assert dataset.name in dataset.metadata["server.tarball-path"]
            assert dataset.metadata["server.status"]["upload"] == "ok"

    def test_index_all(self, server_client: PbenchServerClient, login_user):
        """Wait for datasets to reach the "Indexed" state, and ensure that the
        state and metadata look good
        """

        start = time.time()
        timeout = start + (60.0 * 5.0)
        done = False

        # Test get_list pagination: to avoid forcing a list, we'll count the
        # iterations separately
        count = 0
        datasets = server_client.get_list(limit=5)
        while not done:
            for dataset in datasets:
                count += 1
                metadata = server_client.get_metadata(
                    dataset.resource_id, ["dataset.state", "server.status"]
                )
                state = metadata["dataset.state"]
                assert state in ["Uploaded", "Indexing", "Indexed"]
                if state != "Indexed":
                    assert (
                        time.time() < timeout
                    ), "Exceeded timeout waiting for indexing"
                    time.sleep(30.0)  # sleep for half a minute
                    break
                assert metadata["server.status"]["backup"] == "ok"
                assert metadata["server.status"]["unpack"] == "ok"
                assert metadata["server.status"]["index"] == "ok"
            else:
                done = True
        assert count == len(self.tarballs), "Didn't find all expected datasets"
