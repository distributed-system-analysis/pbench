import collections
import logging
from pathlib import Path

from pbench.common.utils import md5sum, Cleanup


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


class TestCleanup:
    def test_contruct(self, caplog):
        logger = logging.getLogger("test_construct")
        c = Cleanup(logger)
        assert isinstance(c.actions, collections.deque)
        assert len(c.actions) == 0
        assert c.logger is logger

    def test_add(self, caplog):
        class Test:
            def delete(self):
                pass

        logger = logging.getLogger("test_construct")
        c = Cleanup(logger)
        t = Test()
        c.add(t.delete)
        assert c.actions.pop().action == t.delete

    def test_cleanup(self, caplog):
        class Test:
            def __init__(self):
                self.called = []

            def d1(self):
                self.called.append("d1")

            def d2(self):
                self.called.append("d2")

            def d3(self):
                self.called.append("d3")

        logger = logging.getLogger("test_construct")
        c = Cleanup(logger)
        t = Test()
        c.add(t.d2)
        c.add(t.d1)
        c.add(t.d3)

        c.cleanup()
        assert t.called == ["d3", "d1", "d2"]
