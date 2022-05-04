from dateutil import parser as date_parser
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
    @pytest.mark.parametrize(
        "source,iso",
        [
            ("1970-01-01T00:00:00", "1970-01-01T00:00:00+00:00"),
            ("2002-05-16T10:23+00:00", "2002-05-16T10:23:00+00:00"),
            ("2002-05-16T10:23-04:00", "2002-05-16T14:23:00+00:00"),
            ("2020-12-16T09:00:53+05:30", "2020-12-16T03:30:53+00:00"),
        ],
    )
    def test_timehelper(self, source, iso):
        d1 = UtcTimeHelper(date_parser.parse(source))
        d2 = UtcTimeHelper.from_string(source)
        assert d1.to_iso_string() == d2.to_iso_string()
        assert d1.utc_time == d2.utc_time
        assert d1.to_iso_string() == iso
        assert d1.utc_time.isoformat() == d1.to_iso_string()
