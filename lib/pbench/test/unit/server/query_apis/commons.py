from http import HTTPStatus
import itertools
from typing import AnyStr

from dateutil import parser as date_parser
from dateutil import rrule
from dateutil.relativedelta import relativedelta
import pytest
import requests

from pbench.server import JSON
from pbench.server.api.resources import API_METHOD, ApiParams, ParamType, SchemaError
from pbench.server.api.resources.query_apis import ElasticBase
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.test.unit.server.headertypes import HeaderTypes


class Commons:
    """
    Unit testing for all the elasticsearch resources class.

    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    # Declare the common empty search response payload that subclass can use.
    EMPTY_ES_RESPONSE_PAYLOAD = {
        "took": 1,
        "timed_out": False,
        "_shards": {"total": 1, "successful": 1, "skipped": 0, "failed": 0},
        "hits": {
            "total": {"value": 0, "relation": "eq"},
            "max_score": None,
            "hits": [],
        },
    }

    def _setup(
        self,
        cls_obj: ElasticBase = None,
        pbench_endpoint: AnyStr = None,
        elastic_endpoint: AnyStr = None,
        payload: JSON = None,
        bad_date_payload: JSON = None,
        error_payload: JSON = None,
        empty_es_response_payload: JSON = None,
        index_from_metadata: AnyStr = None,
        api_method: AnyStr = API_METHOD.POST,
    ):
        self.cls_obj = cls_obj
        self.pbench_endpoint = pbench_endpoint
        self.elastic_endpoint = elastic_endpoint
        self.payload = payload
        self.bad_date_payload = bad_date_payload
        self.error_payload = error_payload
        self.empty_es_response_payload = empty_es_response_payload
        self.index_from_metadata = index_from_metadata
        self.api_method = api_method

    def build_index(self, server_config, dates):
        """
        Build the index list for query

        Args:
            dates (iterable): list of date strings
        """
        idx = server_config.get("Indexing", "index_prefix") + ".v6.run-data."
        index = "".join([f"{idx}{d}," for d in dates])

        return f"/{index}"

    def build_index_from_metadata(self) -> str:
        """
        Retrieve the list of ES indices from the dataset index
        map metadata based on a given root index name.

        Returns:
            An Elasticsearch query URL string listing the set of
            indices containing documents for the specified root
            index name.
        """
        drb = Dataset.query(name="drb")
        index_map = Metadata.getvalue(dataset=drb, key="server.index-map")
        index_keys = [key for key in index_map if self.index_from_metadata in key]
        return "/" + ",".join(index_keys)

    def date_range(self, start: AnyStr, end: AnyStr) -> list:
        """
        Builds list of range of dates between start and end
        It expects the date to look like YYYY-MM
        """
        date_range = []
        start_date = date_parser.parse(start)
        end_date = date_parser.parse(end)
        assert start_date <= end_date
        first_month = start_date.replace(day=1)
        last_month = end_date + relativedelta(day=31)
        for m in rrule.rrule(rrule.MONTHLY, dtstart=first_month, until=last_month):
            date_range.append(f"{m.year:04}-{m.month:02}")
        return date_range

    def get_expected_status(self, payload: JSON, header: HeaderTypes) -> int:
        """
        Decode the various test cases we use, which are a combination of the
        test case parametrization (for "user" parameter value) and the
        parametrization of the `build_auth_header` fixture (for the API
        authentication header);

        1) If the "user" parameter is given and authentication is missing or
           invalid, we expect UNAUTHORIZED (401) status;
        2) If the "user" parameter is given and authenticated as a different
           non-admin user with "access": "private", we expect FORBIDDEN (403)
        3) If authenticated and a bad "user" parameter is given, we expect
           NOT_FOUND (404)

        Otherwise, we expect success
        """
        has_user = "user" in payload
        u = payload.get("user")
        a = payload.get("access")
        unauthorized = not HeaderTypes.is_valid(header)
        is_admin = header == HeaderTypes.VALID_ADMIN
        if (has_user or a == Dataset.PRIVATE_ACCESS) and unauthorized:
            expected_status = HTTPStatus.UNAUTHORIZED
        elif u == "badwolf" and not unauthorized:
            expected_status = HTTPStatus.NOT_FOUND
        elif u != "drb" and a == Dataset.PRIVATE_ACCESS and not is_admin:
            expected_status = HTTPStatus.FORBIDDEN
        else:
            expected_status = HTTPStatus.OK
        return expected_status

    def make_request_call(
        self, client, url, header: JSON, json: JSON = None, data=None
    ):
        if self.api_method == API_METHOD.GET:
            return client.get(
                url,
                headers=header,
                json=json,
                data=data,
            )
        elif self.api_method == API_METHOD.POST:
            return client.post(
                url,
                headers=header,
                json=json,
                data=data,
            )

    @pytest.mark.parametrize(
        "malformed_token",
        ("malformed", "bear token" "Bearer malformed"),
    )
    def test_malformed_authorization_header(
        self, client, server_config, malformed_token, attach_dataset
    ):
        """
        Test behavior when the Authorization header is present but is not a
        proper Bearer schema.

        TODO: This actually tests behavior with no client authentication, as
        Flask-HTTPTokenAuth hides the validation failure because our query
        APIs select "optional" authentication. If we fix the authentication
        validation to give a 401 (not 403) on bad/missing authentication token,
        we should make the call with user/access parameters that would
        otherwise be allowed for an unauthenticated client (e.g., all public
        data) to distinguish the intent of this case from the path we're
        actually hitting now, which appears to fail as expected but actually
        fails because we're asking for {"access": "private"} data, which is not
        allowed for an unauthenticated client call.
        """
        response = self.make_request_call(
            client,
            server_config.rest_uri + self.pbench_endpoint,
            {"Authorization": malformed_token},
            self.payload,
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_bad_user_name(self, client, server_config, pbench_token):
        """
        Test behavior when authenticated user specifies a non-existent user.
        """
        # The pbench_token fixture logs in as user "drb"
        # Trying to access the data belong to the user "pp"
        user = self.cls_obj.schemas.get_param_by_type(
            self.api_method, ParamType.USER, None
        )
        if not user:
            pytest.skip("skipping " + self.test_bad_user_name.__name__)
        self.payload[user.parameter.name] = "pp"
        response = self.make_request_call(
            client,
            server_config.rest_uri + self.pbench_endpoint,
            {"Authorization": "Bearer " + pbench_token},
            self.payload,
        )
        assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.parametrize(
        "user",
        ("drb", "pp"),
    )
    def test_accessing_user_data_with_invalid_token(
        self, client, server_config, pbench_token, user
    ):
        """
        Test behavior when expired authentication token is provided.

        TODO: This actually tests behavior with no client authentication, as
        Flask-HTTPTokenAuth hides the validation failure because our query
        APIs select "optional" authentication. We expect UNAUTHORIZED (401)
        because we are requesting {"access": "private", "user": xxx} on an
        unauthenticated client connection; because we do not allow an
        unauthenticated client to determine whether a "user" is valid or not,
        either form will fail with "authorization required", which a UI may
        redirect to a login page.
        """
        userp = self.cls_obj.schemas.get_param_by_type(
            self.api_method, ParamType.USER, None
        )
        if not userp:
            pytest.skip(
                "skipping " + self.test_accessing_user_data_with_invalid_token.__name__
            )
        # valid token logout
        response = self.make_request_call(
            client,
            server_config.rest_uri + "/logout",
            {"Authorization": "Bearer " + pbench_token},
        )
        assert response.status_code == HTTPStatus.OK
        self.payload[userp.parameter.name] = user
        response = self.make_request_call(
            client,
            server_config.rest_uri + self.pbench_endpoint,
            {"Authorization": "Bearer " + pbench_token},
            self.payload,
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_missing_json_object(self):
        """
        Test behavior when no JSON payload is given
        """
        with pytest.raises(SchemaError) as exc:
            self.cls_obj.schemas.validate(
                self.api_method, ApiParams(uri=None, query=None, body={})
            )
        assert str(exc.value).startswith("Missing required parameters: ")

    def test_malformed_payload(self, client, server_config, pbench_token):
        """
        Test behavior when payload is not valid JSON
        """
        response = self.make_request_call(
            client,
            server_config.rest_uri + self.pbench_endpoint,
            {
                "Authorization": "Bearer " + pbench_token,
                "Content-Type": "application/json",
            },
            data='{"x":0]',
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert (
            response.json.get("message")
            == "Invalid request payload: '400 Bad Request: The browser (or proxy) sent a request that this server could not understand.'"
        )

    def test_missing_keys(self, client, server_config, pbench_token):
        """
        Test behavior when JSON payload does not contain all required keys.

        Note that Pbench will silently ignore any additional keys that are
        specified but not required.
        """

        def missing_key_helper(keys):
            response = self.make_request_call(
                client,
                server_config.rest_uri + self.pbench_endpoint,
                {"Authorization": "Bearer " + pbench_token},
                keys,
            )
            assert response.status_code == HTTPStatus.BAD_REQUEST
            missing = sorted(set(required_keys) - set(keys))
            assert (
                response.json.get("message")
                == f"Missing required parameters: {','.join(missing)}"
            )

        if self.api_method == API_METHOD.GET:
            parameter_items = self.cls_obj.schemas[
                self.api_method
            ].uri_schema.parameters.items()
        elif self.api_method == API_METHOD.POST:
            parameter_items = self.cls_obj.schemas[
                self.api_method
            ].body_schema.parameters.items()

        required_keys = [
            key for key, parameter in parameter_items if parameter.required
        ]

        all_combinations = []
        for r in range(1, len(parameter_items) + 1):
            for item in itertools.combinations(parameter_items, r):
                tmp_req_keys = [key for key, parameter in item if parameter.required]
                if tmp_req_keys != required_keys:
                    all_combinations.append(item)

        for items in all_combinations:
            keys = {}
            for key, parameter in items:
                if parameter.type == ParamType.ACCESS:
                    keys[key] = "public"
                elif parameter.type == ParamType.DATE:
                    keys[key] = "2020"
                else:
                    keys[key] = "foobar"

            if self.api_method == API_METHOD.POST:
                missing_key_helper(keys)

        # Test in case all of the required keys are missing and some
        # random non-existent key is present in the payload
        if required_keys and self.api_method == API_METHOD.POST:
            missing_key_helper({"notakey": None})

    def test_bad_dates(self, client, server_config, pbench_token):
        """
        Test behavior when a bad date string is given
        """
        if self.api_method == API_METHOD.GET:
            parameter_items = self.cls_obj.schemas[
                self.api_method
            ].uri_schema.parameters.items()
        elif self.api_method == API_METHOD.POST:
            parameter_items = self.cls_obj.schemas[
                self.api_method
            ].body_schema.parameters.items()

        for key, p in parameter_items:
            # Modify date/time key in the payload to make it look invalid
            if p.type == ParamType.DATE and key in self.payload:
                original_date_value = self.payload[key]
                self.payload[key] = "2020-19"
                response = self.make_request_call(
                    client,
                    server_config.rest_uri + self.pbench_endpoint,
                    {"Authorization": "Bearer " + pbench_token},
                    self.payload,
                )
                assert response.status_code == HTTPStatus.BAD_REQUEST
                assert (
                    response.json.get("message")
                    == "Value '2020-19' (str) cannot be parsed as a date/time string"
                )
                self.payload[key] = original_date_value

    def test_empty_query(
        self,
        client,
        server_config,
        query_api,
        find_template,
        build_auth_header,
    ):
        """
        Check proper handling of a query resulting in no Elasticsearch matches.
        PyTest will run this test multiple times with different values of the build_auth_header
        fixture.
        """
        if not self.empty_es_response_payload or not self.elastic_endpoint:
            pytest.skip("skipping " + self.test_empty_query.__name__)
        expected_status = self.get_expected_status(
            self.payload, build_auth_header["header_param"]
        )
        index = self.build_index(
            server_config, self.date_range(self.payload["start"], self.payload["end"])
        )

        response = query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.payload,
            index,
            expected_status,
            headers=build_auth_header["header"],
            status=HTTPStatus.OK,
            json=self.empty_es_response_payload,
        )
        assert response.status_code == expected_status
        if response.status_code == HTTPStatus.OK:
            assert response.json == []

    @pytest.mark.parametrize(
        "exceptions",
        (
            {
                "exception": requests.exceptions.ConnectionError(),
                "status": HTTPStatus.BAD_GATEWAY,
            },
            {
                "exception": requests.exceptions.Timeout(),
                "status": HTTPStatus.GATEWAY_TIMEOUT,
            },
            {
                "exception": requests.exceptions.InvalidURL(),
                "status": HTTPStatus.INTERNAL_SERVER_ERROR,
            },
            {"exception": Exception(), "status": HTTPStatus.INTERNAL_SERVER_ERROR},
            {"exception": ValueError(), "status": HTTPStatus.INTERNAL_SERVER_ERROR},
        ),
    )
    def test_http_exception(
        self,
        server_config,
        query_api,
        query_api_get,
        exceptions,
        find_template,
        pbench_token,
        provide_metadata,
    ):
        """
        Check that an exception in calling Elasticsearch is reported correctly.
        """
        if not self.elastic_endpoint:
            pytest.skip("skipping " + self.test_http_exception.__name__)

        if self.index_from_metadata:
            index = self.build_index_from_metadata()
        else:
            index = self.build_index(
                server_config,
                self.date_range(self.payload["start"], self.payload["end"]),
            )

        if self.api_method == API_METHOD.GET:
            query_api_get(
                self.pbench_endpoint,
                self.elastic_endpoint,
                index,
                exceptions["status"],
                body=exceptions["exception"],
                headers={"Authorization": "Bearer " + pbench_token},
            )
        elif self.api_method == API_METHOD.POST:
            query_api(
                self.pbench_endpoint,
                self.elastic_endpoint,
                self.payload,
                index,
                exceptions["status"],
                body=exceptions["exception"],
                headers={"Authorization": "Bearer " + pbench_token},
            )

    @pytest.mark.parametrize("errors", (400, 500, 409))
    def test_http_error(
        self,
        server_config,
        query_api,
        query_api_get,
        find_template,
        pbench_token,
        provide_metadata,
        errors,
    ):
        """
        Check that an Elasticsearch error is reported correctly through the
        response.raise_for_status() and Pbench handlers.
        """
        if not self.elastic_endpoint:
            pytest.skip("skipping " + self.test_http_error.__name__)

        if self.index_from_metadata:
            index = self.build_index_from_metadata()
        else:
            index = self.build_index(
                server_config,
                self.date_range(self.payload["start"], self.payload["end"]),
            )

        if self.api_method == API_METHOD.GET:
            query_api_get(
                self.pbench_endpoint,
                self.elastic_endpoint,
                index,
                HTTPStatus.BAD_GATEWAY,
                status=errors,
                headers={"Authorization": "Bearer " + pbench_token},
            )
        elif self.api_method == API_METHOD.POST:
            query_api(
                self.pbench_endpoint,
                self.elastic_endpoint,
                self.payload,
                index,
                HTTPStatus.BAD_GATEWAY,
                status=errors,
                headers={"Authorization": "Bearer " + pbench_token},
            )
