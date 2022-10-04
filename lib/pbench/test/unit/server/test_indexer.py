from pbench.server.indexer import ResultData


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
        keyvals = {"name": "mybm"}
        templ = "%benchmark_name%_UID"
        res = ResultData.expand_uid_template(templ, keyvals)
        assert res == "mybm_UID"
        templ = "%controller_host%_UID"
        res = ResultData.expand_uid_template(templ, keyvals, {"controller": "hostA"})
        assert res == "hostA_UID"

    @staticmethod
    def test_value_types():
        templ = "%str%_%int%_%float%_%other%_UID"
        res = ResultData.expand_uid_template(
            templ, {"str": "abc", "int": 123, "float": 45.6789012, "other": []}
        )
        assert res == "abc_123_45.678901_%other%_UID"
