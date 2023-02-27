from http import HTTPStatus
import json
from typing import Callable, Union

from dateutil import parser as date_parser
from flask.wrappers import Response
import pytest

from pbench.server import OperationCode
from pbench.server.api.resources import (
    APIAbort,
    APIInternalError,
    ConversionError,
    InvalidRequestPayload,
    KeywordError,
    ListElementError,
    MissingParameters,
    Parameter,
    ParamType,
    Schema,
    SchemaError,
    UnauthorizedAccess,
    UnsupportedAccessMode,
    UnverifiedUser,
)
from pbench.server.api.resources.query_apis import PostprocessError
from pbench.server.database.models.users import User


class TestExceptions:
    """
    Test exception stringification
    """

    def test_exceptions(self, create_user):
        a = APIAbort(HTTPStatus.IM_USED, "test message")
        assert str(a) == "test message"
        assert repr(a) == "API error 226 : message='test message'"
        a1 = APIAbort(HTTPStatus.CONFLICT)
        assert str(a1) == HTTPStatus.CONFLICT.phrase
        a2 = APIAbort(HTTPStatus.BAD_REQUEST, "SOS", data=1, why=False)
        assert str(a2) == "SOS"
        assert repr(a2) == "API error 400 : message='SOS' {'data': 1, 'why': False}"
        e = UnauthorizedAccess(create_user, OperationCode.READ, "you", "public")
        assert (
            str(e)
            == "User test is not authorized to READ a resource owned by you with public access"
        )
        assert e.user == create_user
        e = UnauthorizedAccess(None, OperationCode.UPDATE, "me", "private")
        assert (
            str(e)
            == "Unauthenticated client is not authorized to UPDATE a resource owned by me with private access"
        )
        s = SchemaError()
        assert str(s) == "Generic schema validation error"
        u = UnverifiedUser("you")
        assert str(u) == "Requestor is unable to verify username 'you'"
        i = InvalidRequestPayload()
        assert str(i) == "Invalid request payload"
        u = UnsupportedAccessMode("him", "private")
        assert str(u) == "Unsupported mode him:private"
        m = MissingParameters(["a", "b"])
        assert str(m) == "Missing required parameters: a,b"
        c = ConversionError({}, "str")
        assert str(c) == "Value {} (dict) cannot be parsed as a str"
        assert c.value == {}
        assert c.http_status == HTTPStatus.BAD_REQUEST
        c = ConversionError(1, "dict", http_status=HTTPStatus.NOT_FOUND)
        assert str(c) == "Value 1 (int) cannot be parsed as a dict"
        assert c.value == 1
        assert c.http_status == HTTPStatus.NOT_FOUND
        p = PostprocessError(HTTPStatus.OK, "all's well", {"param": "none"})
        assert (
            str(p)
            == "Postprocessing error returning 200: \"all's well\" [{'param': 'none'}]"
        )
        assert p.data == {"param": "none"}
        p = PostprocessError(HTTPStatus.BAD_REQUEST, "really bad", None)
        assert str(p) == "Postprocessing error returning 400: 'really bad' [None]"
        assert p.status == HTTPStatus.BAD_REQUEST

    def test_internal_error(self, capinternal, make_logger):
        x = APIInternalError("my error")
        make_logger.error(f"TEST {x.details}")
        r = Response(
            response=json.dumps({"message": x.message}),
            mimetype="application/json",
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )
        capinternal("my error", r)


class TestParamType:
    """
    Tests on the ParamType enum
    """

    def test_enum(self):
        """
        Check basic consistency of the ParamType ENUM
        """
        assert (
            len(ParamType.__members__) == 9
        ), "Number of ParamType ENUM values has changed; confirm test coverage!"
        for n, t in ParamType.__members__.items():
            assert str(t) == t.friendly.upper()
            assert isinstance(t.convert, Callable)

    @pytest.mark.parametrize(
        "ptype,kwd,value,expected",
        (
            (ParamType.ACCESS, None, "PRIVATE", "private"),
            (ParamType.DATE, None, "2021-06-29", date_parser.parse("2021-06-29")),
            (ParamType.INT, None, "1", 1),
            (ParamType.INT, None, 1, 1),
            (ParamType.JSON, None, {"key": "value"}, {"key": "value"}),
            (ParamType.JSON, ["key"], {"key": "value"}, {"key": "value"}),
            (ParamType.KEYWORD, ["Llave"], "llave", "llave"),
            (ParamType.STRING, None, "x", "x"),
            (ParamType.USER, None, "drb", "1"),
        ),
    )
    def test_successful_conversions(
        self, client, monkeypatch, current_user_drb, ptype, kwd, value, expected
    ):
        user = User(
            id="1",
            username="drb",
        )

        def ok(username: str) -> User:
            return user

        monkeypatch.setattr(User, "query", ok)

        param = Parameter("test", ptype, keywords=kwd)
        result = ptype.convert(value, param)
        assert result == expected

    @pytest.mark.parametrize(
        "ptype,value",
        (
            (ParamType.ACCESS, ["foobar"]),  # ACCESS is "public" or "private"
            (ParamType.ACCESS, 0),  # ACCESS must be a string
            (ParamType.DATE, "2021-06-45"),  # few months have 45 days
            (ParamType.DATE, "notadate"),  # not valid date string
            (ParamType.DATE, 1),  # not a string representing a date
            (ParamType.INT, "a"),  # can not convert to an int
            (ParamType.JSON, (1, False)),  # tuple is not JSON
            (ParamType.STRING, {"not": "string"}),  # dict is not string
            (ParamType.USER, False),  # not a user string
            (ParamType.USER, "xyzzy"),  # not a defined username
        ),
    )
    def test_failed_conversions(self, current_user_drb, ptype, value):
        """
        Test unsuccessful parameter conversion / normalization.

        NOTE that we can't test LIST without the element type; we'll test that
        separately.
        """
        param = Parameter("test", ptype)
        with pytest.raises(ConversionError) as exc:
            ptype.convert(value, param)
        assert str(value) in str(exc)

    def test_unauthenticated_username(self, monkeypatch, current_user_none):
        """
        Show that a valid username results in raising UnverifiedUser when the
        client is unauthenticated even when the username exists.
        """
        user = User(
            username="drb",
            id="1",
        )

        def ok(username: str) -> User:
            return user

        monkeypatch.setattr(User, "query", ok)
        with pytest.raises(UnverifiedUser) as exc:
            ParamType.USER.convert("drb", None)
        assert exc.value.username == "drb"

    def test_authenticated_bad_username(self, monkeypatch, current_user_drb):
        """
        Show that an invalid username results in raising ConversionError with
        NOT_FOUND (404) when the client is authenticated.
        """

        def bad(username: str) -> Union[User, None]:
            return None

        monkeypatch.setattr(User, "query", bad)
        with pytest.raises(ConversionError) as exc:
            ParamType.USER.convert("test", None)
        assert exc.value.http_status == HTTPStatus.NOT_FOUND


class TestParameter:
    """
    Tests on the Parameter class
    """

    def test_constructor(self):
        """
        Test the Parameter class constructor with various parameters.
        """
        u = Parameter("test", ParamType.LIST, element_type=ParamType.KEYWORD)
        assert not u.required
        assert u.name == "test"
        assert u.type is ParamType.LIST
        assert u.element_type is ParamType.KEYWORD
        assert u.keywords is None
        assert u.string_list is None

        v = Parameter(
            "test", ParamType.LIST, element_type=ParamType.KEYWORD, string_list="|"
        )
        assert not v.required
        assert v.name == "test"
        assert v.type is ParamType.LIST
        assert v.element_type is ParamType.KEYWORD
        assert v.keywords is None
        assert v.string_list == "|"

        w = Parameter("test", ParamType.KEYWORD, keywords=["a", "b", "c"])
        assert not w.required
        assert w.name == "test"
        assert w.type is ParamType.KEYWORD
        assert w.element_type is None
        assert w.keywords == ["a", "b", "c"]
        assert w.string_list is None

        x = Parameter("test", ParamType.STRING)
        assert not x.required
        assert x.name == "test"
        assert x.type is ParamType.STRING
        assert x.element_type is None
        assert x.keywords is None
        assert x.string_list is None

        y = Parameter("foo", ParamType.JSON, required=True)
        assert y.required
        assert y.name == "foo"
        assert y.type is ParamType.JSON
        assert y.element_type is None
        assert y.keywords is None
        assert y.string_list is None

        z = Parameter("foo", ParamType.JSON, required=False)
        assert not z.required
        assert z.name == "foo"
        assert z.type is ParamType.JSON
        assert z.element_type is None
        assert z.keywords is None
        assert z.string_list is None

    @pytest.mark.parametrize(
        "json,expected",
        (
            ({"data": "yes"}, False),
            ({"data": None}, True),
            ({"foo": "yes"}, True),
            ({"foo": None, "data": "yes"}, False),
        ),
    )
    def test_invalid_required(self, json, expected):
        """
        Test parameter validation of a `required` parameter
        """
        x = Parameter("data", ParamType.STRING, required=True)
        assert x.invalid(json) is expected

    @pytest.mark.parametrize(
        "json",
        (
            {"data": "yes"},
            {"data": None},
            {"foo": "yes"},
            {"foo": None},
        ),
    )
    def test_invalid_optional(self, json):
        """
        An optional parameter is either present or not: either is OK, and the
        value None is acceptable. (In other words, the "invalid" test isn't
        meaningful for required=False parameters, and should always succeed.)
        """
        x = Parameter("data", ParamType.STRING, required=False)
        assert not x.invalid(json)

    @pytest.mark.parametrize(
        "input,expected",
        (
            ("yes", "yes"),
            ("Yes", "yes"),
            ("me.you", "me.you"),
            ("me.You.him", "me.you.him"),
            ("ME.US.HER.THEM", "me.us.her.them"),
        ),
    )
    def test_keyword_namespace(self, input, expected):
        """
        Test parameter normalization for a keyword parameter.
        """
        x = Parameter("data", ParamType.KEYWORD, keywords=["yes", "me"], key_path=True)
        assert x.normalize(input) == expected

    @pytest.mark.parametrize(
        "input,expected",
        (
            ("yes", "yes"),
            ("YES", "yes"),
            ("yES", "yes"),
            ("no", "no"),
            ("No", "no"),
            ("NO", "no"),
            ("maybe", "maybe"),
            ("MaYbE", "maybe"),
            ("Maybe", "maybe"),
            ("MAYBE", "maybe"),
        ),
    )
    def test_keyword_normalization(self, input, expected):
        """
        Test parameter normalization for a keyword parameter.
        """
        x = Parameter("data", ParamType.KEYWORD, keywords=["yes", "no", "maybe"])
        assert x.normalize(input) == expected

    @pytest.mark.parametrize(
        "test",
        (1, {"json": "is not OK"}, ["Yes"], False),
    )
    def test_invalid_keyword_type(self, test):
        """
        Test parameter normalization for invalid keyword parameter values.
        """
        x = Parameter("data", ParamType.KEYWORD, keywords=["Yes", "No"], required=False)
        with pytest.raises(ConversionError) as exc:
            x.normalize(test)
        assert str(test) in str(exc)

    @pytest.mark.parametrize(
        "test",
        ("I'm not sure", "yes!", "ebyam", "yes.foo", "yes."),
    )
    def test_invalid_keyword(self, test):
        """
        Test parameter normalization for invalid keyword parameter values.
        """
        x = Parameter("data", ParamType.KEYWORD, keywords=["Yes", "No"], required=False)
        with pytest.raises(KeywordError) as exc:
            x.normalize(test)
        assert exc.value.parameter == x
        assert exc.value.unrecognized == [test]

    @pytest.mark.parametrize(
        "type,keys,value,expected,delim",
        (
            (None, None, ["yes", "no"], ["yes", "no"], None),
            (None, None, "one", ["one"], ";"),
            (
                ParamType.ACCESS,
                None,
                ["Public", "PRIVATE"],
                ["public", "private"],
                None,
            ),
            (ParamType.INT, None, ["1,2,3"], [1, 2, 3], ","),
            (ParamType.INT, None, ["1", "2", "3"], [1, 2, 3], None),
            (ParamType.INT, None, [1, 2, 3], [1, 2, 3], None),
            (ParamType.KEYWORD, ["Yes", "No"], ["YeS", "nO"], ["yes", "no"], "|"),
            (
                ParamType.KEYWORD,
                ["true", "false"],
                "True;false;TRUE",
                ["true", "false", "true"],
                ";",
            ),
            (ParamType.STRING, None, "yes,no", ["yes", "no"], ","),
            (
                ParamType.KEYWORD,
                None,
                "True+false+BLUE",
                ["true", "false", "blue"],
                "+",
            ),
            (
                ParamType.STRING,
                None,
                ["a,b,c", "yes,no", "maybe", "definitely,not"],
                ["a", "b", "c", "yes", "no", "maybe", "definitely", "not"],
                ",",
            ),
        ),
    )
    def test_list_normalization(self, type, keys, value, expected, delim):
        """
        Test parameter normalization for a list parameter.
        """
        x = Parameter(
            "data", ParamType.LIST, keywords=keys, element_type=type, string_list=delim
        )
        assert x.normalize(value) == expected

    @pytest.mark.parametrize(
        "listtype,keys,path,value",
        (
            (ParamType.ACCESS, None, False, ["sauron", "PRIVATE"]),
            (ParamType.INT, None, False, ["a", "b"]),
            (ParamType.INT, None, False, {"dict": "is-not-a-list-either"}),
            (ParamType.KEYWORD, ["Yes", "No"], False, ["maybe", "nO"]),
            (ParamType.KEYWORD, ["me"], True, ["me."]),
            (ParamType.KEYWORD, ["me"], True, ["me..foo"]),
            (ParamType.KEYWORD, ["me"], True, ["me.foo."]),
            (ParamType.STRING, None, False, 1),
            (ParamType.STRING, None, False, {"dict": "is-not-a-list-either"}),
            (ParamType.STRING, None, False, "a,b,c"),
            (ParamType.STRING, None, False, [False, 1]),
        ),
    )
    def test_invalid_list(self, listtype, keys, path, value):
        """
        Test parameter normalization for a list parameter.
        """
        x = Parameter(
            "data", ParamType.LIST, keywords=keys, element_type=listtype, key_path=path
        )
        with pytest.raises(SchemaError) as exc:
            x.normalize(value)
        if type(value) is list:
            assert exc.type is ListElementError
            assert exc.value.parameter == x
        else:
            assert exc.type is ConversionError


class TestSchema:
    """
    Tests on the Schema class
    """

    schema = Schema(
        Parameter("key1", ParamType.STRING, required=True),
        Parameter("key2", ParamType.JSON),
        Parameter("key3", ParamType.DATE),
    )

    def test_bad_payload(self):
        with pytest.raises(MissingParameters):
            self.schema.validate(None)

    def test_missing_required(self):
        with pytest.raises(MissingParameters):
            self.schema.validate({"key2": "abc"})

    def test_missing_optional(self):
        test = {"key1": "OK"}
        assert test == self.schema.validate(test)

    def test_bad_dates(self):
        with pytest.raises(ConversionError):
            self.schema.validate({"key1": "yes", "key3": "2000-02-56"})

    def test_null_required(self):
        with pytest.raises(MissingParameters):
            self.schema.validate({"key1": None})

    def test_bad_json(self):
        with pytest.raises(ConversionError):
            self.schema.validate({"key1": 1, "key2": "not JSON"})

    def test_all_clear(self):
        payload = {
            "key1": "name",
            "key3": "2021-06-29",
            "key2": {"json": True, "key": "abc"},
        }
        expected = payload.copy()
        expected["key3"] = date_parser.parse(expected["key3"])
        assert expected == self.schema.validate(payload)
