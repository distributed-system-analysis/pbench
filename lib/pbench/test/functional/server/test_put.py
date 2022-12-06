from http import HTTPStatus
from pathlib import Path
import re
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
            assert (
                response.status_code == HTTPStatus.CREATED
            ), f"upload failed with {response.status_code}, {response.text}"
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
                    break
                assert (
                    time.time() < timeout
                ), f"Exceeded timeout: state {state}, status {status}"
                time.sleep(30.0)  # sleep for half a minute
        assert count == len(self.tarballs), "Didn't find all expected datasets"

    def test_upload_again(self, server_client: PbenchServerClient, login_user):
        """Try to upload a dataset we've already uploaded. This should succeed
        but with an OK (200) response instead of CREATED (201)
        """
        duplicate = self.tarballs[0]
        response = server_client.upload(duplicate)
        assert (
            response.status_code == HTTPStatus.OK
        ), f"upload failed with {response.status_code}, {response.text}"

    def test_bad_md5(self, server_client: PbenchServerClient, login_user):
        """Try to upload a new dataset with a bad MD5 value. This should fail."""
        duplicate = self.tarballs[0]
        response = server_client.upload(
            duplicate, md5="this isn't the md5 you're looking for"
        )
        assert (
            response.status_code == HTTPStatus.BAD_REQUEST
        ), f"upload failed with {response.status_code}, {response.text}"
        assert re.match(
            r"MD5 checksum \w+ does not match expected", response.json()["message"]
        )

    def test_bad_name(self, server_client: PbenchServerClient, login_user):
        """Try to upload a new dataset with a bad filename. This should fail."""
        duplicate = self.tarballs[0]
        response = server_client.upload(duplicate, filename="notme")
        assert (
            response.status_code == HTTPStatus.BAD_REQUEST
        ), f"upload failed with {response.status_code}, {response.text}"
        assert (
            response.json()["message"]
            == "File extension not supported, must be .tar.xz"
        )
