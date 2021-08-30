import dateutil
import pytest
from typing import Callable

from pbench.server.api.auth import Auth, UnknownUser
from pbench.server.database.models.users import User
from pbench.server.api.resources import (
    ConversionError,
    InvalidRequestPayload,
    MissingParameters,
    Parameter,
    ParamType,
    Schema,
)


class TestParamType:
    """
    Tests on the ParamType enum
    """

    def test_enum(self):
        assert (
            len(ParamType.__members__) == 6
        ), "Number of ParamType ENUM values has changed; confirm test coverage!"
        for n, t in ParamType.__members__.items():
            assert str(t) == t.friendly.upper()
            assert isinstance(t.convert, Callable)

    @pytest.mark.parametrize(
        "test",
        (
            (ParamType.STRING, "x", "x"),
            (ParamType.JSON, {"key": "value"}, {"key": "value"}),
            (ParamType.DATE, "2021-06-29", dateutil.parser.parse("2021-06-29")),
            (ParamType.USER, "drb", "1"),
            (ParamType.ACCESS, "PRIVATE", "private"),
            (ParamType.LIST, ["drb"], ["drb"]),
            (ParamType.LIST, [], []),
            (ParamType.LIST, ["test1", "test2"], ["test1", "test2"]),
        ),
    )
    def test_successful_conversions(self, client, test, monkeypatch):
        def ok(auth: Auth, username: str) -> User:
            user = User(
                id=1,
                username=username,
                password="password",
                first_name="first_name",
                last_name="last_name",
                email="test@test.com",
            )
            return user

        monkeypatch.setattr(Auth, "verify_user", ok)

        ptype, value, expected = test
        result = ptype.convert(value)
        assert result == expected

    @pytest.mark.parametrize(
        "test",
        (
            (ParamType.STRING, {"not": "string"}),  # dict is not string
            (ParamType.JSON, (1, False)),  # tuple is not JSON
            (ParamType.DATE, "2021-06-45"),  # few months have 45 days
            (ParamType.DATE, "notadate"),  # not valid date string
            (ParamType.DATE, 1),  # not a string representing a date
            (ParamType.USER, "drb"),  # we haven't established a "drb" user
            (ParamType.USER, False),  # not a user string
            (ParamType.ACCESS, "foobar"),  # ACCESS is "public" or "private"
            (ParamType.ACCESS, 0),  # ACCESS must be a string
            (ParamType.LIST, "foobar"),  # Not a list
            (ParamType.LIST, 0),  # Not a list
        ),
    )
    def test_failed_conversions(self, test, monkeypatch):
        def not_ok(auth: Auth, username: str) -> User:
            raise UnknownUser()

        monkeypatch.setattr(Auth, "verify_user", not_ok)

        ptype, value = test
        with pytest.raises(ConversionError) as exc:
            ptype.convert(value)
        assert str(exc).find(str(value))


class TestParameter:
    """
    Tests on the Parameter class
    """

    def test_constructor(self):
        x = Parameter("test", ParamType.STRING)
        assert not x.required
        assert x.name == "test"
        assert x.type is ParamType.STRING

        y = Parameter("foo", ParamType.JSON, required=True)
        assert y.required
        assert y.name == "foo"
        assert y.type is ParamType.JSON

        z = Parameter("foo", ParamType.JSON, required=False)
        assert not z.required
        assert z.name == "foo"
        assert z.type is ParamType.JSON

    @pytest.mark.parametrize(
        "test",
        (
            ({"data": "yes"}, False),
            ({"data": None}, True),
            ({"foo": "yes"}, True),
            ({"foo": None, "data": "yes"}, False),
        ),
    )
    def test_invalid_required(self, test):
        x = Parameter("data", ParamType.STRING, required=True)
        json, expected = test
        assert x.invalid(json) is expected

    @pytest.mark.parametrize(
        "test", ({"data": "yes"}, {"data": None}, {"foo": "yes"}, {"foo": None},),
    )
    def test_invalid_optional(self, test):
        """
        An optional parameter is either present or not: either is OK, and the
        value None is acceptable. (In other words, the "invalid" test isn't
        meaningful for required=False parameters, and should always succeed.)
        """
        x = Parameter("data", ParamType.STRING, required=False)
        json = test
        assert x.invalid(json) is False


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
        with pytest.raises(InvalidRequestPayload):
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
        expected["key3"] = dateutil.parser.parse(expected["key3"])
        assert expected == self.schema.validate(payload)
