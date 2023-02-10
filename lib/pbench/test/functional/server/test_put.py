from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
import os.path
from pathlib import Path
import re
import time

import pytest
from requests.exceptions import HTTPError

from pbench.client import PbenchServerClient
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
            if a == "public":
                metadata = (
                    "server.origin:test,user.pbench.access:public,server.archiveonly:n"
                )
            else:
                metadata = None

            cur_access = 0 if cur_access else 1
            tarballs[Dataset.stem(t)] = Tarball(t, a)
            response = server_client.upload(t, access=a, metadata=metadata)
            assert (
                response.status_code == HTTPStatus.CREATED
            ), f"upload returned unexpected status {response.status_code}, {response.text}"
            print(f"Uploaded {t.name}")

        datasets = server_client.get_list(
            metadata=["dataset.access", "server.tarball-path", "dataset.operations"]
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
                assert dataset.metadata["dataset.operations"]["UPLOAD"]["state"] == "OK"
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
    def test_archive_only(server_client: PbenchServerClient, login_user):
        """Try to upload a new dataset with the archiveonly option set, and
        validate that it doesn't get enabled for unpacking or indexing."""
        tarball = next(iter((TARBALL_DIR / "bad").glob("*.tar.xz")))
        md5 = Dataset.md5(tarball)
        response = server_client.upload(tarball, metadata={"server.archiveonly:y"})
        assert (
            response.status_code == HTTPStatus.CREATED
        ), f"upload returned unexpected status {response.status_code}, {response.text}"
        metadata = server_client.get_metadata(
            md5, ["dataset.operations", "server.archiveonly"]
        )
        assert metadata["server.archiveonly"] is True

        # NOTE: we could wait here; however, the UNPACK operation is only
        # enabled by upload, and INDEX is only enabled by UNPACK: so if they're
        # not here immediately after upload, they'll never be here.
        operations = metadata["dataset.operations"]
        assert "UNPACK" not in operations
        assert "INDEX" not in operations
        assert operations["UPLOAD"]["state"] == "OK"
        assert operations["BACKUP"]["state"] in ("OK", "READY", "WORKING")

        # Delete it so we can run the test case again without manual cleanup
        response = server_client.remove(md5)
        assert (
            response.ok
        ), f"delete failed with {response.status_code}, {response.text}"

    @staticmethod
    def check_indexed(server_client: PbenchServerClient, datasets):
        indexed = []
        not_indexed = []
        try:
            for dataset in datasets:
                print(f"\t... on {dataset.metadata['server.tarball-path']}")
                metadata = server_client.get_metadata(
                    dataset.resource_id, ["dataset.operations"]
                )
                operations = metadata["dataset.operations"]
                if "INDEX" in operations and operations["INDEX"]["state"] == "OK":
                    assert operations["UPLOAD"]["state"] == "OK"
                    assert operations["UNPACK"]["state"] == "OK"
                    assert operations["INDEX"]["state"] == "OK"

                    # Backup is asynchronous: it's OK if it hasn't completed
                    # yet, but must be at least in READY state.
                    assert operations["BACKUP"]["state"] in ("OK", "READY")
                    indexed.append(dataset)
                else:
                    done = ",".join(
                        name for name, op in operations.items() if op["state"] == "OK"
                    )
                    status = ",".join(
                        f"{name}={op['state']}"
                        for name, op in operations.items()
                        if op["state"] != "OK"
                    )
                    print(f"\t\tfinished {done!r}, awaiting {status!r}")
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
            limit=5,
            metadata=[
                "server.tarball-path",
                "dataset.access",
                "server.archiveonly",
                "server.origin",
                "user.pbench.access",
            ],
        )
        not_indexed = []
        try:
            for dataset in not_indexed_raw:
                tp = dataset.metadata["server.tarball-path"]
                if os.path.basename(tp) not in tarball_names:
                    continue
                not_indexed.append(dataset)
                if dataset.metadata["user.pbench.access"] == "public":
                    assert dataset.metadata["server.origin"] == "test"
                    assert dataset.metadata["dataset.access"] == "public"
                    assert dataset.metadata["server.archiveonly"] is False
                else:
                    assert dataset.metadata["dataset.access"] == "private"
                    assert dataset.metadata["server.origin"] is None
                    assert dataset.metadata["server.archiveonly"] is None
                    assert dataset.metadata["user.pbench.access"] is None
        except HTTPError as exc:
            pytest.fail(
                f"Unexpected HTTP error, url = {exc.response.url}, status code"
                f" = {exc.response.status_code}, text = {exc.response.text!r}"
            )

        # For each dataset we find, poll the state until it reaches Indexed
        # state, or until we time out.  Since the cron jobs run once a minute
        # and they start on the minute, we make our 1st check 45 seconds into
        # the next minute, and then check at 45 seconds past the minute until
        # we reached 5 minutes past the original start time.
        oneminute = timedelta(minutes=1)
        now = start = datetime.utcnow()
        timeout = start + timedelta(minutes=5)
        target_int = (
            datetime(now.year, now.month, now.day, now.hour, now.minute)
            + oneminute
            + timedelta(seconds=45)
        )

        while not_indexed:
            print(f"[{(now - start).total_seconds():0.2f}] Checking ...")
            not_indexed, indexed = TestPut.check_indexed(server_client, not_indexed)
            for dataset in indexed:
                tp = dataset.metadata["server.tarball-path"]
                if os.path.basename(tp) not in tarball_names:
                    continue
                count += 1
                print(f"    Indexed {tp}")
            now = datetime.utcnow()
            if not not_indexed or now >= timeout:
                break
            time.sleep((target_int - now).total_seconds())
            target_int += oneminute
            now = datetime.utcnow()
        assert not not_indexed, (
            f"Timed out after {(now - start).total_seconds()} seconds; unindexed datasets: "
            + ", ".join(d.metadata["server.tarball-path"] for d in not_indexed)
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
            response = server_client.remove(resource_id)
            assert (
                response.ok
            ), f"delete failed with {response.status_code}, {response.text}"
            print(f"Deleted {t.name}")
