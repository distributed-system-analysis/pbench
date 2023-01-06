from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
import re
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
            assert (
                response.status_code == HTTPStatus.CREATED
            ), f"upload returned unexpected status {response.status_code}, {response.text}"
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

    def test_upload_again(self, server_client: PbenchServerClient, login_user):
        """Try to upload a dataset we've already uploaded. This should succeed
        but with an OK (200) response instead of CREATED (201)
        """
        duplicate = next(iter(self.tarballs.values())).path
        response = server_client.upload(duplicate)
        assert (
            response.status_code == HTTPStatus.OK
        ), f"upload returned unexpected status {response.status_code}, {response.text}"

    def test_bad_md5(self, server_client: PbenchServerClient, login_user):
        """Try to upload a new dataset with a bad MD5 value. This should fail."""
        duplicate = next(iter(self.tarballs.values())).path
        response = server_client.upload(
            duplicate, md5="this isn't the md5 you're looking for"
        )
        assert (
            response.status_code == HTTPStatus.BAD_REQUEST
        ), f"upload returned unexpected status {response.status_code}, {response.text}"
        assert re.match(
            r"MD5 checksum \w+ does not match expected", response.json()["message"]
        )

    def test_bad_name(self, server_client: PbenchServerClient, login_user):
        """Try to upload a new dataset with a bad filename. This should fail."""
        duplicate = next(iter(self.tarballs.values())).path
        response = server_client.upload(duplicate, filename="notme")
        assert (
            response.status_code == HTTPStatus.BAD_REQUEST
        ), f"upload returned unexpected status {response.status_code}, {response.text}"
        assert (
            response.json()["message"]
            == "File extension not supported, must be .tar.xz"
        )

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
        now = start = time.time()
        timeout = start + (60.0 * 10.0)

        while not_indexed:
            print(f"[{now - start:0.2f}] Checking ...")
            not_indexed, indexed = TestPut.check_indexed(server_client, not_indexed)
            for dataset in indexed:
                count += 1
                print("    Indexed ", dataset.metadata["server.tarball-path"])
            if not not_indexed or now >= timeout:
                break
            time.sleep(30.0)  # sleep for half a minute
            now = time.time()
        assert (
            not not_indexed
        ), f"Timed out after {now - start} seconds; unindexed datasets: " + ", ".join(
            d.metadata["server.tarball-path"] for d in not_indexed
        )
        assert count == len(
            self.tarballs
        ), f"Didn't find all expected datasets, found {count} of {len(self.tarballs)}"
