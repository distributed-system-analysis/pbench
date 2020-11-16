from pathlib import Path

import pytest

from pbench.common.utils import md5sum
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


class TestMd5sum:
    @staticmethod
    def test_md5sum():
        # Reuse the existing file from the server upload fixture.
        filename = "log.tar.xz"
        test_file = Path("./lib/pbench/test/server/fixtures/upload/", filename)
        expected_hash_md5 = open(f"{test_file}.md5", "r").read().split()[0]
        hash_md5 = md5sum(test_file)
        assert (
            hash_md5 == expected_hash_md5
        ), f"Expected MD5 '{expected_hash_md5}', got '{hash_md5}'"
