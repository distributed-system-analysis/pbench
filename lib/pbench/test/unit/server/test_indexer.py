import pytest

import pbench.server.indexer
from pbench.server.indexer import init_indexing, ResultData


class TestResultData_expand_uid_template:
    @staticmethod
    def test_no_keywords():
        templ = "no_keywords_in_this_UID"
        res = ResultData.expand_uid_template(templ, {"this": "that"})
        assert res == templ

    @staticmethod
    def test_found():
        templ = "%this%_UID"
        res = ResultData.expand_uid_template(templ, {"this": "that"})
        assert res == "that_UID"

    @staticmethod
    def test_not_found():
        templ = "%that%_UID"
        res = ResultData.expand_uid_template(templ, {"this": "that"})
        assert res == "%that%_UID"

    @staticmethod
    def test_fallbacks():
        # This UID template is shared with multiple test cases.
        templ = "%benchmark_name%_UID"
        res = ResultData.expand_uid_template(templ, dict(foo=1, bar=2))
        assert res == templ

        # This dictionary is shared with all the other test cases.
        keyvals = {"name": "myname"}

        res = ResultData.expand_uid_template(templ, keyvals)
        assert res == "myname_UID"

        # This UID template is shared with multiple test cases.
        templ = "%controller_host%_UID"
        res = ResultData.expand_uid_template(templ, keyvals)
        assert res == templ

        res = ResultData.expand_uid_template(templ, keyvals, dict(abc=123))
        assert res == templ

        run_d = {"controller": "hostA"}
        res = ResultData.expand_uid_template(templ, keyvals, run_d)
        assert res == "hostA_UID"

    @staticmethod
    def test_value_types():
        templ = "%str%_%int%_%float%_%other%_UID"
        res = ResultData.expand_uid_template(
            templ, {"str": "abc", "int": 123, "float": 45.6789012, "other": []}
        )
        assert res == "abc_123_45.678901_%other%_UID"


def test_init_indexing(monkeypatch, server_config, make_logger):
    called = [False]

    class MockPbenchTemplates:
        def update_templates(self, *args, **kwargs):
            called[0] = True
            assert args[0] == "fake-es-obj", f"args={args!r}, kwargs={kwargs!r}"
            assert not kwargs

    class MockIdxContext:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.templates = MockPbenchTemplates()
            self.es = "fake-es-obj"

    monkeypatch.setattr(pbench.server.indexer, "IdxContext", MockIdxContext)
    try:
        init_indexing("test", server_config, make_logger)
    except Exception as exc:
        pytest.fail(f"Unexpected exception raised: {exc}")
    assert called[0], "Mocked update_templates() was not called"
