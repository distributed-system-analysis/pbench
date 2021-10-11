import pytest
from http import HTTPStatus
from pbench.server.api.resources.query_apis.iteration_samples import IterationSampleRows
from pbench.test.unit.server.headertypes import HeaderTypes
from pbench.test.unit.server.query_apis.commons import Commons


class TestIterationSamplesRows(Commons):
    """
    Unit testing for IterationSamplesRows class.
    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        pytest.scroll_count = 0
        super()._setup(
            cls_obj=IterationSampleRows(client.config, client.logger),
            pbench_endpoint="/dataset/samples/namespace",
            elastic_endpoint="/_search",
            payload={"run_id": "random_md5_string1"},
            index_prefix="result-data-sample",
            index_version=5,
        )

    def test_query(
        self,
        server_config,
        query_api,
        user_ok,
        pbench_token,
        build_auth_header,
        find_template,
        provide_metadata,
    ):
        """
        Check the construction of Elasticsearch query URI and filtering of the
        response body. Note that the mock set up by the attach_dataset fixture
        matches the dataset name to the dataset's owner.
        """
        response_payload = {
            "took": 14,
            "timed_out": "false",
            "_shards": {"total": 5, "successful": 5, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 50, "relation": "eq"},
                "max_score": "null",
                "hits": [],
            },
            "aggregations": {
                "authorization.access": {
                    "buckets": [],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "authorization.owner": {
                    "buckets": [],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "benchmark.bs": {
                    "buckets": [],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "benchmark.clocksource": {
                    "buckets": [],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "benchmark.iodepth": {
                    "buckets": [],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "benchmark.ioengine": {
                    "buckets": [],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "benchmark.name": {
                    "buckets": [{"doc_count": 50, "key": "uperf"}],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "benchmark.numjobs": {
                    "buckets": [],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "benchmark.primary_metric": {
                    "buckets": [{"doc_count": 50, "key": "Gb_sec"}],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "benchmark.protocol": {
                    "buckets": [{"doc_count": 50, "key": "tcp"}],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "benchmark.rate_tolerance_failure": {
                    "buckets": [],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "benchmark.rw": {
                    "buckets": [],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "benchmark.test_type": {
                    "buckets": [{"doc_count": 50, "key": "stream"}],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "benchmark.uid": {
                    "buckets": [
                        {
                            "doc_count": 50,
                            "key": "benchmark_name:uperf-controller_host:dhcp31-171.perf.lab.eng.bos.redhat.com",
                        }
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "benchmark.uid_tmpl": {
                    "buckets": [
                        {
                            "doc_count": 50,
                            "key": "benchmark_name:%benchmark_name%-controller_host:%controller_host%",
                        }
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "iteration.name": {
                    "buckets": [
                        {"doc_count": 10, "key": "1-tcp_stream-131072B-2i"},
                        {"doc_count": 10, "key": "1-tcp_stream-131072B-2i-fail1"},
                        {"doc_count": 10, "key": "1-tcp_stream-131072B-2i-fail2"},
                        {"doc_count": 10, "key": "1-tcp_stream-131072B-2i-fail3"},
                        {"doc_count": 10, "key": "1-tcp_stream-131072B-2i-fail4"},
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "run.config": {
                    "buckets": [{"doc_count": 50, "key": "npalaska-dhcp31-171"}],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "run.controller": {
                    "buckets": [
                        {
                            "doc_count": 50,
                            "key": "dhcp31-171.perf.lab.eng.bos.redhat.com",
                        }
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "run.id": {
                    "buckets": [
                        {"doc_count": 50, "key": "f3a37c9891a78886639e3bc00e3c5c4e"}
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "run.name": {
                    "buckets": [
                        {
                            "doc_count": 50,
                            "key": "uperf_npalaska-dhcp31-171_2021.07.14T15.30.22",
                        }
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "run.script": {
                    "buckets": [{"doc_count": 50, "key": "uperf"}],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "run.toolsgroup": {
                    "buckets": [],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "sample.category": {
                    "buckets": [],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "sample.client_hostname": {
                    "buckets": [
                        {"doc_count": 25, "key": "127.0.0.1"},
                        {"doc_count": 25, "key": "all"},
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "sample.field": {
                    "buckets": [],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "sample.group": {
                    "buckets": [],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "sample.measurement_title.raw": {
                    "buckets": [{"doc_count": 50, "key": "Gb_sec"}],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "sample.measurement_type": {
                    "buckets": [{"doc_count": 50, "key": "throughput"}],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "sample.name": {
                    "buckets": [
                        {"doc_count": 10, "key": "sample1"},
                        {"doc_count": 10, "key": "sample2"},
                        {"doc_count": 10, "key": "sample3"},
                        {"doc_count": 10, "key": "sample4"},
                        {"doc_count": 10, "key": "sample5"},
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "sample.pgid": {
                    "buckets": [],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "sample.server_hostname": {
                    "buckets": [
                        {"doc_count": 25, "key": "127.0.0.1"},
                        {"doc_count": 25, "key": "all"},
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "sample.uid": {
                    "buckets": [
                        {
                            "doc_count": 25,
                            "key": "client_hostname:127.0.0.1-server_hostname:127.0.0.1-server_port:20010",
                        },
                        {
                            "doc_count": 25,
                            "key": "client_hostname:all-server_hostname:all-server_port:all",
                        },
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "sample.uid_tmpl": {
                    "buckets": [
                        {
                            "doc_count": 50,
                            "key": "client_hostname:%client_hostname%-server_hostname:%server_hostname%-server_port:%server_port%",
                        }
                    ],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
            },
        }
        index = self.build_index_from_metadata(find_template)

        if HeaderTypes.is_valid(build_auth_header["header_param"]):
            expected_status = HTTPStatus.OK
        else:
            expected_status = HTTPStatus.FORBIDDEN

        response = query_api(
            self.pbench_endpoint,
            self.elastic_endpoint,
            self.payload,
            index,
            expected_status,
            json=response_payload,
            status=HTTPStatus.OK,
            headers=build_auth_header["header"],
        )
        if expected_status == HTTPStatus.OK:
            res_json = response.json
            expected_result = {
                "authorization.access": [],
                "authorization.owner": [],
                "benchmark.bs": [],
                "benchmark.clocksource": [],
                "benchmark.iodepth": [],
                "benchmark.ioengine": [],
                "benchmark.name": ["uperf"],
                "benchmark.numjobs": [],
                "benchmark.primary_metric": ["Gb_sec"],
                "benchmark.protocol": ["tcp"],
                "benchmark.rate_tolerance_failure": [],
                "benchmark.rw": [],
                "benchmark.test_type": ["stream"],
                "benchmark.uid": [
                    "benchmark_name:uperf-controller_host:dhcp31-171.perf.lab.eng.bos.redhat.com"
                ],
                "benchmark.uid_tmpl": [
                    "benchmark_name:%benchmark_name%-controller_host:%controller_host%"
                ],
                "iteration.name": [
                    "1-tcp_stream-131072B-2i",
                    "1-tcp_stream-131072B-2i-fail1",
                    "1-tcp_stream-131072B-2i-fail2",
                    "1-tcp_stream-131072B-2i-fail3",
                    "1-tcp_stream-131072B-2i-fail4",
                ],
                "run.config": ["npalaska-dhcp31-171"],
                "run.controller": ["dhcp31-171.perf.lab.eng.bos.redhat.com"],
                "run.id": ["f3a37c9891a78886639e3bc00e3c5c4e"],
                "run.name": ["uperf_npalaska-dhcp31-171_2021.07.14T15.30.22"],
                "run.script": ["uperf"],
                "run.toolsgroup": [],
                "sample.category": [],
                "sample.client_hostname": ["127.0.0.1", "all"],
                "sample.field": [],
                "sample.group": [],
                "sample.measurement_title.raw": ["Gb_sec"],
                "sample.measurement_type": ["throughput"],
                "sample.name": ["sample1", "sample2", "sample3", "sample4", "sample5"],
                "sample.pgid": [],
                "sample.server_hostname": ["127.0.0.1", "all"],
                "sample.uid": [
                    "client_hostname:127.0.0.1-server_hostname:127.0.0.1-server_port:20010",
                    "client_hostname:all-server_hostname:all-server_port:all",
                ],
                "sample.uid_tmpl": [
                    "client_hostname:%client_hostname%-server_hostname:%server_hostname%-server_port:%server_port%"
                ],
            }

            assert expected_result == res_json
