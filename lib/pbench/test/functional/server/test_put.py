from dataclasses import dataclass
from http import HTTPStatus
import os.path
from pathlib import Path
import re
import time

import pytest
from requests.exceptions import HTTPError

from pbench.client import API, PbenchServerClient
from pbench.client.types import Dataset

TARBALL_DIR = Path("lib/pbench/test/functional/server/tarballs")


@dataclass
class Tarball:
    """Record the tarball path and the uploaded access value"""

    path: Path
    access: str


class TestPut:
    """These tests depend on the order of their definition to execute properly.

    That is, `test_index_all` assumes that all the tar balls in the
    `TARBALL_DIR` were uploaded successfully by `test_upload_all`, and that it
    is run before `test_delete` (otherwise it won't find any data sets to
    verify were indexed). In turn, `test_delete` expects to be run after
    `test_upload_all` in order to find the data sets to be deleted.
    """

    @staticmethod
    def test_upload_all(server_client: PbenchServerClient, login_user):
        """Upload each of the pregenerated tarballs, and perform some basic
        sanity checks on the resulting server state.
        """
        print(" ... reporting behaviors ...")

        tarballs: dict[str, Tarball] = {}
        access = ["private", "public"]
        cur_access = 0

        for t in TARBALL_DIR.glob("*.tar.xz"):
            a = access[cur_access]
            cur_access = 0 if cur_access else 1
            tarballs[Dataset.stem(t)] = Tarball(t, a)
            response = server_client.upload(t, access=a)
            assert (
                response.status_code == HTTPStatus.CREATED
            ), f"upload returned unexpected status {response.status_code}, {response.text}"
            print(f"Uploaded {t.name}")

        datasets = server_client.get_list(
            metadata=["dataset.access", "server.tarball-path", "server.status"]
        )
        found = frozenset({d.name for d in datasets})
        expected = frozenset(tarballs.keys())
        assert expected.issubset(found), f"expected {expected!r}, found {found!r}"
        try:
            for dataset in datasets:
                if dataset.name not in expected:
                    continue
                t = tarballs[dataset.name]
                assert dataset.name in dataset.metadata["server.tarball-path"]
                assert dataset.metadata["server.status"]["upload"] == "ok"
                assert t.access == dataset.metadata["dataset.access"]
        except HTTPError as exc:
            pytest.fail(
                f"Unexpected HTTP error, url = {exc.response.url}, status"
                f" code = {exc.response.status_code}, text = {exc.response.text!r}"
            )

    @staticmethod
    def test_upload_again(server_client: PbenchServerClient, login_user):
        """Try to upload a dataset we've already uploaded. This should succeed
        but with an OK (200) response instead of CREATED (201)
        """
        duplicate = next(iter(TARBALL_DIR.glob("*.tar.xz")))
        response = server_client.upload(duplicate)
        assert (
            response.status_code == HTTPStatus.OK
        ), f"upload returned unexpected status {response.status_code}, {response.text}"

    @staticmethod
    def test_bad_md5(server_client: PbenchServerClient, login_user):
        """Try to upload a new dataset with a bad MD5 value. This should fail."""
        duplicate = next(iter(TARBALL_DIR.glob("*.tar.xz")))
        response = server_client.upload(
            duplicate, md5="this isn't the md5 you're looking for"
        )
        assert (
            response.status_code == HTTPStatus.BAD_REQUEST
        ), f"upload returned unexpected status {response.status_code}, {response.text}"
        assert re.match(
            r"MD5 checksum \w+ does not match expected", response.json()["message"]
        )

    @staticmethod
    def test_bad_name(server_client: PbenchServerClient, login_user):
        """Try to upload a new dataset with a bad filename. This should fail."""
        duplicate = next(iter(TARBALL_DIR.glob("*.tar.xz")))
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
        try:
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
        except HTTPError as exc:
            pytest.fail(
                f"Unexpected HTTP error, url = {exc.response.url}, status code"
                f" = {exc.response.status_code}, text = {exc.response.text!r}"
            )
        return not_indexed, indexed

    @staticmethod
    def test_index_all(server_client: PbenchServerClient, login_user):
        """Wait for datasets to reach the "Indexed" state, and ensure that the
        state and metadata look good.

        Requires that test_upload_all has been run successfully, and that
        test_delete has NOT been run yet.
        """
        tarball_names = frozenset(t.name for t in TARBALL_DIR.glob("*.tar.xz"))

        print(" ... reporting behaviors ...")

        # Test get_list pagination: to avoid forcing a list, we'll count the
        # iterations separately. (Note that this is really an implicit test
        # of the paginated datasets/list API and the get_list generator, which
        # one could argue belong in a separate test case; I'll likely refactor
        # this later when I add GET tests.)
        count = 0
        not_indexed_raw = server_client.get_list(
            limit=5, metadata=["server.tarball-path"]
        )
        not_indexed = []
        try:
            for dataset in not_indexed_raw:
                tp = dataset.metadata["server.tarball-path"]
                if os.path.basename(tp) not in tarball_names:
                    continue
                not_indexed.append(dataset)
        except HTTPError as exc:
            pytest.fail(
                f"Unexpected HTTP error, url = {exc.response.url}, status code"
                f" = {exc.response.status_code}, text = {exc.response.text!r}"
            )

        # For each dataset we find, poll the state until it reaches Indexed
        # state, or until we time out.
        now = start = time.time()
        timeout = start + (60.0 * 10.0)

        while not_indexed:
            print(f"[{now - start:0.2f}] Checking ...")
            not_indexed, indexed = TestPut.check_indexed(server_client, not_indexed)
            for dataset in indexed:
                tp = dataset.metadata["server.tarball-path"]
                if os.path.basename(tp) not in tarball_names:
                    continue
                count += 1
                print(f"    Indexed {tp}")
            if not not_indexed or now >= timeout:
                break
            time.sleep(30.0)  # sleep for half a minute
            now = time.time()
        assert (
            not not_indexed
        ), f"Timed out after {now - start} seconds; unindexed datasets: " + ", ".join(
            d.metadata["server.tarball-path"] for d in not_indexed
        )
        assert (
            len(tarball_names) == count
        ), f"Didn't find all expected datasets, found {count} of {len(tarball_names)}"

    @staticmethod
    def test_delete_all(server_client: PbenchServerClient, login_user):
        """Verify we can delete each previously uploaded dataset.

        Requires that test_upload_all has been run successfully.
        """
        print(" ... reporting behaviors ...")

        datasets = server_client.get_list()
        datasets_hash = {}
        try:
            for dataset in datasets:
                datasets_hash[f"{dataset.name}.tar.xz"] = dataset.resource_id
        except HTTPError as exc:
            pytest.fail(
                f"Unexpected HTTP error, url = {exc.response.url}, status code"
                f" = {exc.response.status_code}, text = {exc.response.text!r}"
            )
        for t in TARBALL_DIR.glob("*.tar.xz"):
            resource_id = datasets_hash.get(t.name)
            assert resource_id, f"Expected to find tar ball {t.name} to delete"
            response = server_client.post(
                api=API.DATASETS_DELETE,
                uri_params={"dataset": resource_id},
                raise_error=False,
            )
            assert response.ok, f"{response.text}"
            print(f"Deleted {t.name}")
            response = server_client.head(
                api=API.DATASETS_METADATA,
                uri_params={"dataset": resource_id},
            )
            assert response.status_code == 404, f"{response!r}"
