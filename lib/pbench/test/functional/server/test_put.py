from pathlib import Path
import sys
import time

from pbench.client import PbenchServerClient
from pbench.client.types import Dataset

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
        expected = sorted(Dataset.stem(t) for t in self.tarballs)
        assert found == expected
        for dataset in datasets:
            assert dataset.name in dataset.metadata["server.tarball-path"]
            assert dataset.metadata["server.status"]["upload"] == "ok"

    def test_index_all(self, server_client: PbenchServerClient, login_user):
        """Wait for datasets to reach the "Indexed" state, and ensure that the
        state and metadata look good
        """

        # Test get_list pagination: to avoid forcing a list, we'll count the
        # iterations separately. (Note that this is really an implicit test
        # of the paginated datasets/list API and the get_list generator, which
        # one could argue belong in a separate test case; I'll likely refactor
        # this later when I add GET tests.)
        count = 0
        datasets = server_client.get_list(limit=5)

        # For each dataset we find, poll the state until it reaches Indexed
        # state, or until we time out.
        start = time.time()
        timeout = start + (60.0 * 5.0)

        for dataset in datasets:
            count += 1
            while True:
                metadata = server_client.get_metadata(
                    dataset.resource_id, ["dataset.state", "server.status"]
                )
                state = metadata["dataset.state"]
                assert state in ["Uploaded", "Indexing", "Indexed"]
                if state == "Indexed":
                    assert metadata["server.status"]["backup"] == "ok"
                    assert metadata["server.status"]["unpack"] == "ok"
                    assert metadata["server.status"]["index"] == "ok"
                    break
                print(f"Dataset {dataset.name} [{state}]", file=sys.stderr)
                assert time.time() < timeout, "Exceeded timeout waiting for indexing"
                time.sleep(30.0)  # sleep for half a minute
        assert count == len(self.tarballs), "Didn't find all expected datasets"
