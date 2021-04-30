from pathlib import Path

from pbench.common.utils import md5sum


class TestMd5sum:
    @staticmethod
    def test_md5sum():
        # Reuse the existing file from the server upload fixture.
        filename = "log.tar.xz"
        test_file = Path("./lib/pbench/test/unit/server/fixtures/upload/", filename)
        expected_length = test_file.stat().st_size
        expected_hash_md5 = open(f"{test_file}.md5", "r").read().split()[0]
        length, hash_md5 = md5sum(test_file)
        assert (
            length == expected_length
        ), f"Expected length '{expected_length}', got '{length}'"
        assert (
            hash_md5 == expected_hash_md5
        ), f"Expected MD5 '{expected_hash_md5}', got '{hash_md5}'"
