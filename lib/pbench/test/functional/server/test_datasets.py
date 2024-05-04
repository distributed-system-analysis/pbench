from configparser import ConfigParser
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
import os.path
from pathlib import Path
import re
import time

import dateutil.parser
import pytest
from requests import Response
from requests.exceptions import HTTPError

from pbench.client import API, PbenchServerClient
from pbench.client.types import Dataset, JSONOBJECT

TARBALL_DIR = Path("lib/pbench/test/functional/server/tarballs")
SPECIAL_DIR = TARBALL_DIR / "special"
NOMETADATA = SPECIAL_DIR / "nometadata.tar.xz"
DUPLICATE_NAME = SPECIAL_DIR / "fio_rw_2018.02.01T22.40.57.tar.xz"
SHORT_EXPIRATION_DAYS = 10


def utc_from_str(date: str) -> datetime:
    """Convert a date string to a UTC datetime

    Args:
        date: date/time string

    Returns:
        UTC datetime object
    """
    return dateutil.parser.parse(date).replace(tzinfo=timezone.utc)


def expiration() -> str:
    """Calculate a datetime for dataset deletion from "now".

    Returns:
        A "YYYY-MM-DD" string representing the day when a dataset uploaded
        "now" would be deleted.
    """
    retention = timedelta(days=730)
    d = datetime.now(timezone.utc) + retention
    return f"{d:%Y-%m-%d}"


@dataclass
class Tarball:
    """Record the tarball path and the uploaded access value"""

    path: Path
    access: str


def all_tarballs() -> list[Path]:
    return list(TARBALL_DIR.glob("*.tar.xz")) + list(SPECIAL_DIR.glob("*.tar.xz"))


class TestPut:
    """Test success and failure cases of PUT dataset upload"""

    @pytest.mark.dependency(name="upload", scope="session")
    def test_upload_all(self, server_client: PbenchServerClient, login_user):
        """Upload each of the pregenerated tarballs, and perform some basic
        sanity checks on the resulting server state.
        """
        print(" ... uploading tarballs ...")

        tarballs: dict[str, Tarball] = {}
        access = ["private", "public"]
        cur_access = 0

        # We're going to make some datasets expire "soon" (much sooner than the
        # default) so we can test filtering typed metadata.
        expire_soon = datetime.now(timezone.utc) + timedelta(days=SHORT_EXPIRATION_DAYS)

        for t in TARBALL_DIR.glob("*.tar.xz"):
            a = access[cur_access]
            if a == "public":
                metadata = (
                    "server.origin:test,user.pbench.access:public,server.archiveonly:n:bool",
                    f"server.deletion:'{expire_soon:%Y-%m-%d %H:%M%z}'",
                )
            else:
                metadata = None

            cur_access = 0 if cur_access else 1
            name = Dataset.stem(t)
            md5 = Dataset.md5(t)
            tarballs[name] = Tarball(t, a)
            response = server_client.upload(t, access=a, metadata=metadata)
            assert (
                response.status_code == HTTPStatus.CREATED
            ), f"upload returned unexpected status {response.status_code}, {response.text} ({t})"
            metabench = server_client.get_metadata(md5, ["server.benchmark"])
            benchmark = metabench["server.benchmark"]
            assert response.json() == {
                "message": "File successfully uploaded",
                "name": name,
                "resource_id": md5,
                "notes": [
                    f"Identified benchmark workload {benchmark!r}.",
                    f"Expected expiration date is {expiration()}.",
                ],
            }
            assert response.headers["location"] == server_client._uri(
                API.DATASETS_INVENTORY, {"dataset": md5, "target": ""}
            )
            print(f"\t... uploaded {name}: {a}")

        datasets = server_client.get_list(
            metadata=[
                "dataset.access",
                "dataset.metalog.pbench.script",
                "server.benchmark",
                "server.tarball-path",
                "dataset.operations",
            ]
        )
        found = frozenset({d.name for d in datasets})
        expected = frozenset(tarballs.keys())
        assert expected.issubset(found), f"expected {expected!r}, found {found!r}"
        try:
            for dataset in datasets:
                if dataset.name not in expected:
                    continue
                t = tarballs[dataset.name]

                # Check that the tarball path has the expected file name and
                # that it's in the expected isolation directory.
                path = Path(dataset.metadata["server.tarball-path"])
                assert path.name == f"{dataset.name}.tar.xz"
                assert path.parent.name == dataset.resource_id

                # Check that the upload was successful
                assert dataset.metadata["dataset.operations"]["UPLOAD"]["state"] == "OK"
                assert (
                    dataset.metadata["dataset.metalog.pbench.script"]
                    == dataset.metadata["server.benchmark"]
                )
                assert t.access == dataset.metadata["dataset.access"]
        except HTTPError as exc:
            pytest.fail(
                f"Unexpected HTTP error, url = {exc.response.url}, status"
                f" code = {exc.response.status_code}, text = {exc.response.text!r}"
            )

    @pytest.mark.dependency(depends=["upload"], scope="session")
    def test_upload_again(self, server_client: PbenchServerClient, login_user):
        """Try to upload a dataset we've already uploaded. This should succeed
        but with an OK (200) response instead of CREATED (201)
        """
        duplicate = next(iter(TARBALL_DIR.glob("*.tar.xz")))
        name = Dataset.stem(duplicate)
        md5 = Dataset.md5(duplicate)
        response = server_client.upload(duplicate)
        assert (
            response.status_code == HTTPStatus.OK
        ), f"upload returned unexpected status {response.status_code}, {response.text}"
        assert response.json() == {
            "message": "Dataset already exists",
            "name": name,
            "resource_id": md5,
        }
        assert response.headers["location"] == server_client._uri(
            API.DATASETS_INVENTORY, {"dataset": md5, "target": ""}
        )

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
        """Test `server.archiveonly`

        Try to upload a new dataset with the archiveonly option set, and
        validate that it doesn't get enabled for unpacking or indexing.
        """
        tarball = SPECIAL_DIR / "fio_mock_2020.01.19T00.18.06.tar.xz"
        name = Dataset.stem(tarball)
        md5 = Dataset.md5(tarball)
        response = server_client.upload(tarball, metadata={"server.archiveonly:y"})
        assert (
            response.status_code == HTTPStatus.CREATED
        ), f"upload {name} returned unexpected status {response.status_code}, {response.text}"
        assert response.json() == {
            "message": "File successfully uploaded",
            "name": name,
            "resource_id": md5,
            "notes": [
                "Identified benchmark workload 'fio'.",
                f"Expected expiration date is {expiration()}.",
                "Indexing is disabled by 'archive only' setting.",
            ],
        }
        assert response.headers["location"] == server_client._uri(
            API.DATASETS_INVENTORY, {"dataset": md5, "target": ""}
        )
        metadata = server_client.get_metadata(
            md5,
            [
                "dataset.metalog.pbench.script",
                "dataset.operations",
                "server.archiveonly",
                "server.benchmark",
            ],
        )
        assert metadata["dataset.metalog.pbench.script"] == "fio"
        assert metadata["server.archiveonly"] is True
        assert metadata["server.benchmark"] == "fio"

        # NOTE: we could wait here; however, the UNPACK operation is only
        # enabled by upload, and INDEX is only enabled by UNPACK: so if they're
        # not here immediately after upload, they'll never be here.
        operations = metadata["dataset.operations"]
        assert operations["UPLOAD"]["state"] == "OK"
        assert "INDEX" not in operations

    @staticmethod
    def test_no_metadata(server_client: PbenchServerClient, login_admin):
        """Test handling for a tarball without a metadata.log.

        Try to upload a new tarball with no `metadata.log` file, and
        validate that it doesn't get enabled for unpacking or indexing.

        This will be owned by the "testadmin" user to allow queries by owner.
        """
        tarball = NOMETADATA
        name = Dataset.stem(tarball)
        md5 = Dataset.md5(tarball)
        response = server_client.upload(tarball, access="public")
        assert (
            response.status_code == HTTPStatus.CREATED
        ), f"upload {name} returned unexpected status {response.status_code}, {response.text}"

        assert response.json() == {
            "message": "File successfully uploaded",
            "name": name,
            "resource_id": md5,
            "notes": [
                "Results archive is missing 'nometadata/metadata.log'.",
                "Identified benchmark workload 'unknown'.",
                f"Expected expiration date is {expiration()}.",
                "Indexing is disabled by 'archive only' setting.",
            ],
        }
        assert response.headers["location"] == server_client._uri(
            API.DATASETS_INVENTORY, {"dataset": md5, "target": ""}
        )
        metadata = server_client.get_metadata(
            md5,
            [
                "dataset.operations",
                "dataset.metalog",
                "server.archiveonly",
                "server.benchmark",
            ],
        )
        assert metadata["dataset.metalog"] == {
            "pbench": {"name": name, "script": "unknown"}
        }
        assert metadata["server.benchmark"] == "unknown"
        assert metadata["server.archiveonly"] is True
        operations = metadata["dataset.operations"]
        assert operations["UPLOAD"]["state"] == "OK"
        assert "INDEX" not in operations

    @staticmethod
    def test_duplicate_name(server_client: PbenchServerClient, login_user):
        """Test handling for a tarball with a duplicate name but unique MD5.

        In automated cloud testing we frequently see datasets started with
        similar parameters at about the same time: these can result in
        datasets with the same filename but distinct MD5 hashes (e.g., run
        on different systems and/or at slightly different times that round to
        the same second). Make sure that the server handles this gracefully.
        """
        tarball = DUPLICATE_NAME
        name = Dataset.stem(tarball)
        md5 = Dataset.md5(tarball)
        response = server_client.upload(tarball)
        assert (
            response.status_code == HTTPStatus.CREATED
        ), f"upload {name} returned unexpected status {response.status_code}, {response.text}"

        assert response.json() == {
            "message": "File successfully uploaded",
            "name": name,
            "resource_id": md5,
            "notes": [
                "Identified benchmark workload 'fio'.",
                f"Expected expiration date is {expiration()}.",
            ],
        }
        assert response.headers["location"] == server_client._uri(
            API.DATASETS_INVENTORY, {"dataset": md5, "target": ""}
        )
        metadata = server_client.get_metadata(
            md5,
            [
                "dataset.operations",
                "server.archiveonly",
                "server.benchmark",
            ],
        )
        assert metadata["server.benchmark"] == "fio"
        assert not metadata["server.archiveonly"]
        operations = metadata["dataset.operations"]
        assert operations["UPLOAD"]["state"] == "OK"
        assert "INDEX" in operations

    @staticmethod
    def check_indexed(server_client: PbenchServerClient, datasets):
        indexed = []
        not_indexed = []
        try:
            for dataset in datasets:
                print(f"\t... on {dataset.name}")
                metadata = server_client.get_metadata(
                    dataset.resource_id, ["dataset.operations"]
                )
                operations = metadata["dataset.operations"]
                if "INDEX" in operations and operations["INDEX"]["state"] in (
                    "FAILED",
                    "OK",
                ):
                    assert operations["INDEX"]["state"] == "OK"
                    indexed.append(dataset)
                else:
                    done = ",".join(
                        name for name, op in operations.items() if op["state"] == "OK"
                    )
                    undone = []
                    for name, op in operations.items():
                        if op["state"] != "OK":
                            undone.append(f"{name}={op['state']}(msg={op['message']})")
                    status = ",".join(undone)
                    print(f"\t\tfinished {done!r}, awaiting {status!r}")
                    not_indexed.append(dataset)
        except HTTPError as exc:
            pytest.fail(
                f"Unexpected HTTP error, url = {exc.response.url}, status code"
                f" = {exc.response.status_code}, text = {exc.response.text!r}"
            )
        return not_indexed, indexed

    @pytest.mark.dependency(name="index", depends=["upload"], scope="session")
    def test_index_all(self, server_client: PbenchServerClient, login_user):
        """Wait for indexable datasets to reach the "Indexed" state, and ensure
        that the state and metadata look good.
        """

        # We can't use a set (or dict) here as we have duplicate tarball names
        # and we need to retain the original count of matches.
        tarball_names = [i.name for i in all_tarballs()]
        print(" ... reporting dataset status ...")

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
                "server.deletion",
                "user.pbench.access",
            ],
        )
        not_indexed = []
        try:
            for dataset in not_indexed_raw:
                tp = Path(dataset.metadata["server.tarball-path"])

                # Ignore unexpected and non-indexable datasets
                if (
                    tp.name not in tarball_names
                    or dataset.metadata["server.archiveonly"]
                ):
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

        # For each dataset we find, poll the state until it has been indexed,
        # or until we time out. The indexer runs once a minute slightly after
        # the minute, so we make our 1st check 45 seconds into the next minute,
        # and then check at 45 seconds past the minute until we reach 5 minutes
        # past the original start time.
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
                count += 1
                print(f"\t... indexed {dataset.name}")
            now = datetime.utcnow()
            if not not_indexed or now >= timeout:
                break
            time.sleep((target_int - now).total_seconds())
            target_int += oneminute
            now = datetime.utcnow()
        assert not not_indexed, (
            f"Timed out after {(now - start).total_seconds()} seconds; unindexed datasets: "
            + ", ".join(d.name for d in not_indexed)
        )


class TestIndexing:
    @pytest.mark.dependency(name="detail", depends=["index"], scope="session")
    def test_details(self, server_client: PbenchServerClient, login_user):
        """Check access to indexed data

        Perform a GET /datasets/details/{id} to be confirm whether indexed run
        data is available.
        """
        print(" ... checking dataset RUN index ...")
        datasets = server_client.get_list(
            metadata=["dataset.metalog.pbench"], owner="tester"
        )
        for d in datasets:

            # Query the dataset's indices: if the returned object is empty,
            # there are none.
            indices = server_client.get(API.DATASETS, {"dataset": d.resource_id})
            indexed = bool(indices.json())
            print(
                f"\t... checking run details for {d.name} "
                f"({'' if indexed else 'not '} indexed)"
            )
            response = server_client.get(
                API.DATASETS_DETAIL, {"dataset": d.resource_id}, raise_error=False
            )
            detail = response.json()
            if indexed:
                assert (
                    response.ok
                ), f"DETAILS for {d.name} failed with {detail['message']}"
                assert (
                    d.metadata["dataset.metalog.pbench"]["script"]
                    == detail["runMetadata"]["script"]
                ), f"Unexpected details {detail}"
            else:
                assert (
                    response.status_code == HTTPStatus.NOT_FOUND
                ), f"Unexpected {response.json()['message']}"
                assert response.json()["message"] == "Dataset has no 'run-data' data"


class TestList:
    @pytest.mark.dependency(name="list_none", depends=["upload"], scope="session")
    def test_list_anonymous(self, server_client: PbenchServerClient):
        """List all datasets without a login.

        We should see only published datasets. We don't care whether there are
        pre-existing datasets in this case: we'll simply confirm that every one
        we see is public. We do care that we don't get an empty list, since we
        uploaded datasets with access public.
        """
        datasets = server_client.get_list(metadata=["dataset.access"])
        count = 0

        for dataset in datasets:
            assert dataset.metadata["dataset.access"] == "public"
            count += 1

        assert count > 1

    @pytest.mark.dependency(name="list_api_key", depends=["upload"], scope="session")
    def test_list_api_key(self, server_client: PbenchServerClient, login_user):
        """List "my" datasets using an API key.

        We should see all datasets owned by the tester account, both private
        and public. That is, using the API key is the same as using the normal
        auth token.
        """
        server_client.create_api_key()
        assert server_client.api_key, "No API key was set on the session"
        datasets = server_client.get_list(mine="true")

        # Figure out which datasets we expect to find, which is "all_tarballs"
        # minus the NOMETADATA dataset which we uploaded under a different
        # account.
        expected = [
            {"resource_id": Dataset.md5(f), "name": Dataset.stem(f), "metadata": {}}
            for f in all_tarballs()
            if f != NOMETADATA
        ]
        expected.sort(key=lambda e: e["resource_id"])
        actual = [d.json for d in datasets]
        assert expected == actual
        server_client.remove_api_key()
        assert not server_client.api_key, "API key was not removed as expected"

    @pytest.mark.dependency(name="list_or", depends=["upload"], scope="session")
    def test_list_filter_or(self, server_client: PbenchServerClient, login_user):
        """Check a simple OR filter list.

        Authorized as our "tester" user, we can see all the datasets we've
        uploaded. Try a filtered list choosing datasets run with the "fio"
        script OR the "linpack" script. Only those datasets should appear: we
        check the list against a glob of our upload source directory.
        """
        fio_names = {Dataset.stem(t) for t in TARBALL_DIR.glob("*fio*.tar.xz")}
        linpack_names = {Dataset.stem(t) for t in TARBALL_DIR.glob("*linpack*.tar.xz")}
        expected = fio_names | linpack_names
        datasets = server_client.get_list(
            metadata=["dataset.metalog.pbench.name"],
            owner="tester",
            filter=[
                "^dataset.metalog.pbench.script:fio",
                "^dataset.metalog.pbench.script:linpack",
            ],
        )

        actual = set(d.metadata["dataset.metalog.pbench.name"] for d in datasets)
        assert actual >= expected, f"Missing datasets: {expected - actual}"

    @pytest.mark.dependency(name="list_and", depends=["upload"], scope="session")
    def test_list_filter_and(self, server_client: PbenchServerClient, login_user):
        """Check a simple AND filter list.

        Authorized as our "tester" user, we can see all the datasets we've
        uploaded. Try a filtered list choosing datasets which are public AND
        were created in 2018.

        NOTE: the original "owner", "access", "start", "end", and "name"
        filters are supported and implicitly linked as AND; their matching is
        also more "friendly" in some cases, e.g., being case-insensitive. In
        this case we're using "dataset.access".
        """
        datasets = server_client.get_list(
            metadata=["dataset.metalog.pbench.date", "dataset.access"],
            owner="tester",
            filter=[
                "dataset.metalog.pbench.date:~2018",
                "dataset.access:public",
            ],
        )

        for dataset in datasets:
            date = dataset.metadata["dataset.metalog.pbench.date"]
            access = dataset.metadata["dataset.access"]
            assert access == "public", f"Dataset {dataset.name} access is {access}"
            assert "2018" in date, f"Dataset {dataset.name} date is {date}"

    @pytest.mark.dependency(name="list_all", depends=["upload"], scope="session")
    def test_list_filter_and_or(self, server_client: PbenchServerClient, login_user):
        """Check a simple AND-OR filter list.

        Authorized as our "tester" user, we can see all the datasets we've
        uploaded. Try a filtered list choosing datasets which are public AND
        created in either 2018 or 2019.
        """
        datasets = server_client.get_list(
            metadata=["dataset.metalog.pbench.date", "dataset.access"],
            owner="tester",
            filter=[
                "dataset.access:public",
                "^dataset.metalog.pbench.date:~2018",
                "^dataset.metalog.pbench.date:~2019",
            ],
        )

        for dataset in datasets:
            date = dataset.metadata["dataset.metalog.pbench.date"]
            access = dataset.metadata["dataset.access"]
            assert access == "public", f"Dataset {dataset.name} access is {access}"
            assert (
                "2018" in date or "2019" in date
            ), f"Dataset {dataset.name} date is {date}"

    @pytest.mark.dependency(name="list_type", depends=["upload"], scope="session")
    def test_list_filter_typed(self, server_client: PbenchServerClient, login_user):
        """Test filtering using typed matches.

        We set an early "server.deletion" time on alternating datasets as we
        uploaded them. Now prove that we can use a typed "date" filter to find
        them. We'll further validate that none of the other datasets we
        uploaded from TARBALL_DIR should have been returned.
        """
        test_sets = {}
        for t in TARBALL_DIR.glob("*.tar.xz"):
            r = Dataset.md5(t)
            m = server_client.get_metadata(
                r,
                ["dataset.name", "server.deletion"],
            )
            test_sets[r] = m
        soonish = datetime.now(timezone.utc) + timedelta(days=SHORT_EXPIRATION_DAYS * 2)

        datasets = server_client.get_list(
            metadata=["server.deletion"],
            owner="tester",
            # NOTE: using weird "US standard" date notation here minimizes
            # the risk of succeeding via a simple alphanumeric comparison.
            filter=[f"server.deletion:<'{soonish:%m/%d/%Y %H:%M%z}':date"],
        )

        # Confirm that the returned datasets match
        for dataset in datasets:
            deletion = utc_from_str(dataset.metadata["server.deletion"])
            assert (
                deletion < soonish
            ), f"Filter returned {dataset.name}, with expiration out of range ({deletion:%Y-%m-%d})"
            test_sets.pop(dataset.resource_id, None)

        # Confirm that the remaining TARBALL_DIR datasets don't match
        for r, m in test_sets.items():
            deletion = utc_from_str(m["server.deletion"])
            assert (
                deletion >= soonish
            ), f"Filter failed to return {m['dataset.name']}, with expiration in range ({deletion:%Y-%m-%d})"

    @pytest.mark.dependency(name="list_owner", depends=["upload"], scope="session")
    def test_list_filter_owner_mine(
        self, server_client: PbenchServerClient, login_user
    ):
        """Check that we can filter by dataset owner

        The NOMETADATA dataset is owned by "testadmin" but public: verify that
        the filter shows all "tester" datasets but not NOMETADATA.
        """
        mine = sorted(Dataset.md5(x) for x in all_tarballs() if x != NOMETADATA)
        datasets = server_client.get_list(
            metadata=["dataset.owner"],
            filter=["dataset.owner:tester"],
        )
        datasets = list(datasets)
        for d in datasets:
            assert d.metadata["dataset.owner"] == "tester"
        assert sorted(d.resource_id for d in datasets) == mine

    @pytest.mark.dependency(name="list_owner_sort", depends=["upload"], scope="session")
    def test_list_filter_owner_sort(
        self, server_client: PbenchServerClient, login_user
    ):
        """Check that we can filter and sort by dataset owner

        Authorized as our "tester" user, we can see all the datasets we've
        uploaded, including the NOMETADATA dataset uploaded (and published)
        by the "testadmin" user.
        """
        all = sorted(Dataset.md5(x) for x in all_tarballs())
        datasets = server_client.get_list(
            metadata=["dataset.owner"],
            filter=["dataset.owner:~test"],
            sort=["dataset.owner:desc"],
        )

        # With a single "testadmin" dataset and descending sort order, we
        # expect to find the "testadmin" owner at the end of the list with the
        # remainder all owned by "tester".
        datasets = list(datasets)
        assert datasets[-1].metadata["dataset.owner"] == "testadmin"
        for d in datasets[:-1]:
            assert d.metadata["dataset.owner"] == "tester"
        assert sorted(d.resource_id for d in datasets) == all

    @pytest.mark.dependency(name="list_int_sort", depends=["upload"], scope="session")
    def test_list_int_sort(self, server_client: PbenchServerClient, login_user):
        """Check that we can sort "raw size" as an integer"""
        all = sorted(Dataset.md5(x) for x in all_tarballs())
        datasets = list(
            server_client.get_list(
                metadata=["dataset.metalog.run.raw_size"],
                sort=["dataset.metalog.run.raw_size:desc:int"],
            )
        )

        # Assert that we got all the expected datasets
        assert sorted(d.resource_id for d in datasets) == all

        # Some (e.g., the no-metadata and some benchmarks) won't have a "raw
        # size" field: we expect PostgreSQL to return them at the beginning of
        # the list even though arguably "smaller" than any real value.
        last_size = None
        for d in datasets:
            s = d.metadata["dataset.metalog.run.raw_size"]
            if s is None:
                assert last_size is None, "Null value sorted after a non-null"
                continue
            size = int(s)
            assert last_size is None or size <= last_size
            last_size = size
        assert last_size is not None

    @pytest.mark.dependency(name="list_date_sort", depends=["upload"], scope="session")
    def test_list_date_sort(self, server_client: PbenchServerClient, login_user):
        """Check that we can sort run start timestamp as a date"""
        all = sorted(Dataset.md5(x) for x in all_tarballs())
        datasets = list(
            server_client.get_list(
                metadata=["dataset.metalog.run.start_run"],
                sort=["dataset.metalog.run.start_run:desc:date"],
            )
        )

        # Assert that we got all the expected datasets
        assert sorted(d.resource_id for d in datasets) == all

        last_date = None
        for d in datasets:
            s = d.metadata["dataset.metalog.run.start_run"]
            if s is None:
                assert last_date is None, "Null value sorted after a non-null"
                continue
            date = dateutil.parser.parse(s)
            assert last_date is None or date <= last_date
            last_date = date
        assert last_date is not None


class TestInventory:
    """Validate APIs involving tarball inventory"""

    @pytest.mark.dependency(name="contents", depends=["upload"], scope="session")
    def test_contents(self, server_client: PbenchServerClient, login_user):
        """Check that we can retrieve the root directory TOC

        NOTE: the TOC API currently uses the Elasticsearch run-toc index, so
        the datasets must have gotten through indexing.
        """
        datasets = server_client.get_list(
            owner="tester", metadata=["server.archiveonly"]
        )

        datasets_returned = False
        for dataset in datasets:
            datasets_returned = True
            response = server_client.get(
                API.DATASETS_CONTENTS,
                {"dataset": dataset.resource_id, "target": ""},
                raise_error=False,
            )
            assert (
                response.ok
            ), f"CONTENTS {dataset.name} failed {response.status_code}:{response.json()['message']}"
            json = response.json()

            archive_only = dataset.metadata["server.archiveonly"]

            # assert that we have directories and/or files: an empty root
            # directory is technically possible, but not legal unless it's a
            # trivial "archiveonly" dataset. NOTE: this will also fail if
            # either the "directories" or "files" JSON keys are missing.
            assert archive_only or json["directories"] or json["files"]

            # Even if they're empty, both values must be lists
            assert isinstance(json["directories"], list)
            assert isinstance(json["files"], list)
            assert json["name"] == ""
            assert json["type"] == "DIRECTORY"
            assert json["uri"] == response.url

            # We expect to find at least a metadata.log at the top level of the
            # tarball unless the dataset is marked archive-only.
            assert archive_only or (
                "metadata.log" in (f["name"] for f in json["files"])
            )

            # All files and directories reported must have a valid API URI
            for d in json["directories"]:
                uri = server_client._uri(
                    API.DATASETS_CONTENTS,
                    {"dataset": dataset.resource_id, "target": d["name"]},
                )
                assert d["uri"] == uri, f"{d['name']} uri is incorrect: {d['uri']}"

            for f in json["files"]:
                uri = server_client._uri(
                    API.DATASETS_INVENTORY,
                    {"dataset": dataset.resource_id, "target": f["name"]},
                )
                assert f["uri"] == uri, f"{f['name']} uri is incorrect: {f['uri']}"
        assert datasets_returned  # We successfully checked at least one dataset

    @pytest.mark.dependency(name="visualize", depends=["upload"], scope="session")
    def test_visualize(self, server_client: PbenchServerClient, login_user):
        """Check that we can generate visualization data from a dataset

        Identify all "uperf" runs (pbench-uperf wrapper script) as that's all
        we can currently support.
        """
        datasets = server_client.get_list(
            owner="tester",
            filter=["server.benchmark:uperf"],
        )

        for dataset in datasets:
            response = server_client.get(
                API.DATASETS_VISUALIZE, {"dataset": dataset.resource_id}
            )
            assert (
                response.ok
            ), f"VISUALIZE {dataset.name} failed {response.status_code}:{response.json()['message']}"
            json = response.json()
            assert json["status"] == "success"
            assert json["benchmark"] == "uperf"
            assert "csv_data" in json
            assert json["json_data"]["dataset_name"] == dataset.name
            assert isinstance(json["json_data"]["data"], list)

    @pytest.mark.dependency(name="compare", depends=["upload"], scope="session")
    def test_compare(self, server_client: PbenchServerClient, login_user):
        """Check that we can compare two datasets.

        Identify all "uperf" runs (pbench-uperf wrapper script) as that's all
        we can currently support.
        """
        datasets = server_client.get_list(
            owner="tester",
            filter=["server.benchmark:uperf"],
        )

        candidates = [dataset.resource_id for dataset in datasets]

        # We need at least two "uperf" datasets to compare, but they can be the
        # same ... so if we only have one (the normal case), duplicate it.
        if len(candidates) == 1:
            candidates.append(candidates[0])

        # In the unlikely event we find multiple uperf datasets, compare only
        # the first two.
        response = server_client.get(
            API.DATASETS_COMPARE, params={"datasets": candidates[:2]}
        )
        json = response.json()
        assert (
            response.ok
        ), f"COMPARE {candidates[:2]} failed {response.status_code}:{json['message']}"
        assert json["status"] == "success"
        assert json["benchmark"] == "uperf"
        assert isinstance(json["json_data"]["data"], list)

    @pytest.mark.dependency(name="inventory", depends=["upload"], scope="session")
    def test_inventory(self, server_client: PbenchServerClient, login_user):
        """Check that we can retrieve inventory files from a tarball

        The most universal tarball artifact is "metadata.log", which is
        mandatory for all "non-archive-only" datasets. So find them all and
        ensure that each yields the same metadata.log that the server read
        during upload.
        """

        def read_metadata(response: Response) -> JSONOBJECT:
            metadata_log = ConfigParser(interpolation=None)
            metadata_log.read_string(response.text)
            metadata = {s: dict(metadata_log.items(s)) for s in metadata_log.sections()}
            return metadata

        datasets = server_client.get_list(
            owner="tester",
            metadata=["dataset.metalog"],
            filter=["server.archiveonly:false:bool"],
        )

        for dataset in datasets:
            response = server_client.get(
                API.DATASETS_INVENTORY,
                {"dataset": dataset.resource_id, "target": "metadata.log"},
            )

            # Note that Werkzeug doesn't understand anything special about the
            # ".log" filetype, but will apply a better content-type header for
            # file types it understands like ".json".
            assert response.headers["content-type"] == "application/octet-stream"
            assert (
                response.headers["content-disposition"]
                == "inline; filename=metadata.log"
            )
            assert (
                response.ok
            ), f"INVENTORY {dataset.name} failed {response.status_code}:{response.json()['message']}"
            meta = read_metadata(response)
            assert meta == dataset.metadata["dataset.metalog"]

            # Test that the content-disposition header has the proper full
            # filename for the tarball itself.
            response = server_client.get(
                API.DATASETS_INVENTORY,
                {"dataset": dataset.resource_id, "target": ""},
            )

            # Werkzeug quotes filenames it thinks might be "suspect"; rather
            # than try to reverse engineer the logic, check it piecemeal.
            assert response.headers["content-disposition"].startswith(
                "attachment; filename="
            )
            assert f"{dataset.name}.tar.xz" in response.headers["content-disposition"]


class TestUpdate:
    @pytest.mark.dependency(name="publish", depends=["index"], scope="session")
    @pytest.mark.parametrize("access", ("public", "private"))
    def test_publish(self, server_client: PbenchServerClient, login_user, access):
        """Test updating the access of the datasets"""
        expected = "public" if access == "private" else "private"
        datasets = server_client.get_list(access=access, mine="true")
        print(f" ... updating {access} datasets to {expected} ...")
        for dataset in datasets:
            response = server_client.update(
                dataset.resource_id, access=expected, raise_error=False
            )
            print(f"\t ... updating {dataset.name} to {expected!r}")
            assert (
                response.ok
            ), f"Indexed dataset {dataset.name} failed to update with {response.json()['message']}"
            meta = server_client.get_metadata(
                dataset.resource_id, metadata="dataset.access"
            )
            assert (
                meta["dataset.access"] == expected
            ), f"{dataset.name} access not changed to {expected}"

    @pytest.mark.dependency(
        name="transfer", depends=["list_owner", "list_owner_sort"], scope="session"
    )
    def test_transfer(self, server_client: PbenchServerClient, login_admin):
        """Change the ownership of our NOMETADATA to tester

        This tests the ownership change, but also allows the delete_all test to
        delete all the datasets we uploaded from the unprivileged "tester".
        """
        id = Dataset.md5(NOMETADATA)
        response = server_client.update(id, owner="tester", raise_error=False)
        assert (
            response.ok
        ), f"Dataset {Dataset.stem(NOMETADATA)} failed to update with {response.json()['message']}"
        meta = server_client.get_metadata(id, metadata="dataset.owner")
        assert (
            meta["dataset.owner"] == "tester"
        ), f"{Dataset.stem(NOMETADATA)} owner not changed to 'tester'"


class TestDelete:
    @pytest.mark.dependency(
        depends=[
            "detail",
            "index",
            "list_all",
            "list_and",
            "list_none",
            "list_or",
            "list_type",
            "publish",
            "transfer",
        ],
        scope="session",
    )
    def test_delete_all(self, server_client: PbenchServerClient, login_user):
        """Verify we can delete each previously uploaded dataset.

        Requires that test_upload_all has been run successfully.
        """
        if os.environ.get("KEEP_DATASETS"):
            pytest.skip(reason="Skipping dataset deletion on request")

        print(" ... reporting behaviors ...")

        try:
            datasets = server_client.get_list()
        except HTTPError as exc:
            pytest.fail(
                f"Unexpected HTTP error, url = {exc.response.url}, status code"
                f" = {exc.response.status_code}, text = {exc.response.text!r}"
            )

        # Create a set of all tarball names we expect. We'll delete any dataset
        # returned by the "get_list" query which is on this list. (NOTE that
        # the "set" collapses duplicate names; but it doesn't matter here as
        # they'll both match.)
        all = set(Dataset.stem(d) for d in all_tarballs())
        for d in datasets:
            if d.name in all:
                response = server_client.remove(d.resource_id)
                assert (
                    response.ok
                ), f"delete {d.name} failed with {response.status_code}, {response.text}"
                print(f"\t ... deleted {d.name}")
