import logging
from pathlib import Path

import pytest

from pbench.common.utils import Cleanup, CleanupNotCallable, Md5Result, md5sum


class TestMd5sum:
    @staticmethod
    def test_md5sum():
        # Reuse the existing file from the server upload fixture.
        filename = "log.tar.xz"
        test_file = Path("./lib/pbench/test/unit/server/fixtures/upload/", filename)
        expected_length = test_file.stat().st_size
        expected_hash_md5 = open(f"{test_file}.md5", "r").read().split()[0]
        retval = md5sum(test_file)

        # Validate the return as a named tuple
        assert isinstance(retval, Md5Result)
        assert retval.length == expected_length
        assert retval.md5_hash == expected_hash_md5

        # Validate as a plain list tuple
        length, hash_md5 = retval
        assert (
            length == expected_length
        ), f"Expected length '{expected_length}', got '{length}'"
        assert (
            hash_md5 == expected_hash_md5
        ), f"Expected MD5 '{expected_hash_md5}', got '{hash_md5}'"


class TestCleanup:
    def test_bad_add(self, caplog):
        logger = logging.getLogger("test_bad_add")
        c = Cleanup(logger)

        with pytest.raises(CleanupNotCallable):
            c.add(1)

    def test_cleanup(self, caplog):
        class FakeObject:
            def __init__(self):
                self.called = []

            def d1(self):
                self.called.append("d1")

            def d2(self):
                self.called.append("d2")

            def d3(self):
                self.called.append("d3")

        logger = logging.getLogger("test_cleanup")
        c = Cleanup(logger)
        t = FakeObject()
        c.add(t.d2)
        c.add(t.d1)
        c.add(t.d3)

        c.cleanup()
        assert t.called == ["d3", "d1", "d2"]

    def test_cleanup_throws(self, caplog):
        class FakeObject:
            def __init__(self):
                self.called = []

            def d1(self):
                self.called.append("d1")

            def d2(self):
                self.called.append("d2")

            def d3(self):
                raise Exception("I'm a bad apple")

        logger = logging.getLogger("test_cleanup")
        c = Cleanup(logger)
        t = FakeObject()
        c.add(t.d2)
        c.add(t.d3)
        c.add(t.d1)

        c.cleanup()
        assert t.called == ["d1", "d2"]
