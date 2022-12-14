from dataclasses import dataclass
from pathlib import Path
import time

from pbench.client import PbenchServerClient
from pbench.client.types import Dataset

TARBALL_DIR = Path("lib/pbench/test/functional/server/tarballs")


@dataclass
class Tarball:
    """Record the tarball path and the uploaded access value"""

    path: Path
    access: str


class TestPut:
    tarballs: dict[str, Tarball] = {}

    def test_upload_all(self, server_client: PbenchServerClient, login_user):
        """Upload each of the pregenerated tarballs, and perform some basic
        sanity checks on the resulting server state.
        """
        access = ["private", "public"]
        cur_access = 0

        for t in TARBALL_DIR.glob("*.tar.xz"):
            a = access[cur_access]
            cur_access = 0 if cur_access else 1
            self.tarballs[Dataset.stem(t)] = Tarball(t, a)
            response = server_client.upload(t, access=a)
            assert response.ok
        datasets = server_client.get_list(
            metadata=["dataset.access", "server.tarball-path", "server.status"]
        )
        found = sorted(d.name for d in datasets)
        expected = sorted(self.tarballs.keys())
        assert found == expected
        for dataset in datasets:
            t = self.tarballs[dataset.name]
            assert dataset.name in dataset.metadata["server.tarball-path"]
            assert dataset.metadata["server.status"]["upload"] == "ok"
            assert t.access == dataset.metadata["dataset.access"]

    @staticmethod
    def check_indexed(server_client: PbenchServerClient, datasets):
        indexed = []
        not_indexed = []
        for dataset in datasets:
            print(f"\t... on {dataset.metadata['server.tarball-path']}")
            metadata = server_client.get_metadata(
                dataset.resource_id, ["dataset.state", "server.status"]
            )
            state = metadata["dataset.state"]
            status = metadata["server.status"]
            stats = set(status.keys()) if status else set()
            if state == "Indexed" and {"unpack", "index"} <= stats:
                # Don't wait for backup, and don't fail if we haven't as
                # it's completely independent from unpack/index; but if we
                # have backed up, check that the status was successful.
                if "backup" in stats:
                    assert status["backup"] == "ok"
                assert status["unpack"] == "ok"
                assert status["index"] == "ok"
                indexed.append(dataset)
            else:
                not_indexed.append(dataset)
        return not_indexed, indexed

    def test_index_all(self, server_client: PbenchServerClient, login_user):
        """Wait for datasets to reach the "Indexed" state, and ensure that the
        state and metadata look good
        """
        print(" ... reporting behaviors ...")

        # Test get_list pagination: to avoid forcing a list, we'll count the
        # iterations separately. (Note that this is really an implicit test
        # of the paginated datasets/list API and the get_list generator, which
        # one could argue belong in a separate test case; I'll likely refactor
        # this later when I add GET tests.)
        count = 0
        not_indexed = server_client.get_list(limit=5, metadata=["server.tarball-path"])

        # For each dataset we find, poll the state until it reaches Indexed
        # state, or until we time out.
        start = time.time()
        timeout = start + (60.0 * 10.0)

        while True:
            now = time.time()
            print(f"[{now - start:0.2f}] Checking ...")
            not_indexed, indexed = TestPut.check_indexed(server_client, not_indexed)
            for dataset in indexed:
                count += 1
                print(
                    "    Indexed ",
                    dataset.metadata["server.tarball-path"],
                )
            if not not_indexed:
                break
            if time.time() < timeout:
                time.sleep(30.0)  # sleep for half a minute
            else:
                print("Exceeded timeout (10 minutes), still not indexed:")
                for dataset in not_indexed:
                    print(dataset.metadata["server.tarball-path"])
        assert count == len(
            self.tarballs
        ), f"Didn't find all expected datasets, found {count} of {len(self.tarballs)}"
