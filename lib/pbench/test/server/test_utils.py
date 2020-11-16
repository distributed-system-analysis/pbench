import pytest
from pbench.server.utils import filesize_bytes


_sizes = [("  10  ", 10)]
for i, mult in [
    ("B", 1),
    ("b", 1),
    ("KB", 1024),
    ("Kb", 1024),
    ("kB", 1024),
    ("kb", 1024),
    ("MB", 2 ** 20),
    ("GB", 2 ** 30),
    ("TB", 2 ** 40),
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
