import datetime

from freezegun.api import freeze_time
import pytest

from pbench.server.utils import UtcTimeHelper, filesize_bytes


_sizes = [("  10  ", 10)]
for i, mult in [
    ("B", 1),
    ("b", 1),
    ("KB", 1024),
    ("Kb", 1024),
    ("kB", 1024),
    ("kb", 1024),
    ("MB", 2**20),
    ("GB", 2**30),
    ("TB", 2**40),
]:
    matrix = [
        (f"10{i}", 10 * mult),
        (f"10 {i}", 10 * mult),
        (f"10   {i}", 10 * mult),
        (f"10{i}   ", 10 * mult),
        (f"10 {i}   ", 10 * mult),
    ]
    _sizes.extend(matrix)


class TestFilesizeBytes:
    @staticmethod
    def test_filesize_bytes():
        for size, exp_val in _sizes:
            res = filesize_bytes(size)
            assert (
                res == exp_val
            ), f"string '{size}', improperly converted to {res}, expected {exp_val}"
        with pytest.raises(Exception):
            res = filesize_bytes("bad")


class TestUtcTimeHelper:
    @freeze_time("1970-01-01")
    def test_naive(self):
        d = UtcTimeHelper(datetime.datetime.now())
        assert d.to_iso_string() == "1970-01-01T00:00:00+00:00"
        assert d.utc_time.isoformat() == d.to_iso_string()

    @freeze_time("2002-05-16T10:23+00:00")
    def test_aware_utc(self):
        d = UtcTimeHelper(datetime.datetime.now(datetime.timezone.utc))
        assert d.to_iso_string() == "2002-05-16T10:23:00+00:00"

    @freeze_time("2002-05-16T10:23-04:00")
    def test_aware_local(self):
        d = UtcTimeHelper(
            datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-4)))
        )
        assert d.to_iso_string() == "2002-05-16T14:23:00+00:00"
