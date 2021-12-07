from http import HTTPStatus

import pytest
from werkzeug.exceptions import InternalServerError

from pbench.server.api.resources.query_apis.datasets.namespace_and_rows import (
    SampleNamespace,
    SampleValues,
)
from pbench.server.database.models.datasets import Dataset, Metadata
from pbench.test.unit.server.query_apis.commons import Commons


class TestSamplesNamespace(Commons):
    """
    Unit testing for SamplesNamespace class.
    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        super()._setup(
            cls_obj=SampleNamespace(client.config, client.logger),
            pbench_endpoint="/datasets/namespace/iterations",
            elastic_endpoint="/_search",
            payload={"run_id": "random_md5_string1"},
            index_from_metadata="result-data-sample",
        )

    def test_with_no_index_document(self, client, server_config):
        """
        Check the Namespace API when no index name is provided
        """
        # remove the last component of the pbench_endpoint
        incorrect_endpoint = "/".join(self.pbench_endpoint.split("/")[:-1])
        response = client.get(f"{server_config.rest_uri}{incorrect_endpoint}")
        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_with_incorrect_index_document(self, client, server_config, pbench_token):
        """
        Check the Namespace API when an incorrect index name is provided.
        currently we only support iterations (result-data-samples) and
        timeseries (result-data) documents
        """
        incorrect_endpoint = "/".join(self.pbench_endpoint.split("/")[:-1]) + "/test"
        response = client.post(
            f"{server_config.rest_uri}{incorrect_endpoint}",
            headers={"Authorization": "Bearer " + pbench_token},
            json=self.payload,
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_get_aggregatable_fields(self, attach_dataset):
        mappings = {
            "properties": {
                "sample": {
                    "properties": {
                        "@idx": {"type": "long"},
                        "name": {"type": "keyword"},
                        "name_text": {"type": "text"},
                        "measurement_type": {"type": "keyword"},
                        "measurement_idx": {"type": "long"},
                        "measurement_title1": {
                            "type": "text",
                            "fields": {"raw": {"type": "keyword"}},
                        },
                        "measurement_title2": {
                            "type": "text",
                            "fields": {
                                "raw1": {
                                    "type": "text",
                                    "fields": {"raw2": {"type": "keyword"}},
                                }
                            },
                        },
                        "measurement_title3": {
                            "type": "text",
                            "fields": {
                                "raw1": {
                                    "type": "text",
                                    "fields": {"raw2": {"type": "text"}},
                                }
                            },
                        },
                        "uid": {"type": "keyword"},
                    }
                }
            }
        }
        result = self.cls_obj.get_aggregatable_fields(mappings)
        assert result == [
            "sample.@idx",
            "sample.name",
            "sample.measurement_type",
            "sample.measurement_idx",
            "sample.measurement_title1.raw",
            "sample.measurement_title2.raw1.raw2",
            "sample.uid",
        ]

    def test_query(
        self,
        server_config,
        query_api,
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
                            "key": "benchmark_name:uperf-controller_host:host.name.com",
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
                    "buckets": [{"doc_count": 50, "key": "npalaska"}],
                    "doc_count_error_upper_bound": 0,
                    "sum_other_doc_count": 0,
                },
                "run.controller": {
                    "buckets": [{"doc_count": 50, "key": "host.name.com"}],
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
                        {"doc_count": 50, "key": "uperf_npalaska_2021.07.14T15.30.22"}
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
        index = self.build_index_from_metadata()

        # get_expected_status() expects to read username and access from the
        # JSON client payload, however this API acquires that information
        # from the Dataset. Construct a fake payload corresponding to the
        # attach_dataset fixture.
        auth_json = {"user": "drb", "access": "private"}
        expected_status = self.get_expected_status(
            auth_json, build_auth_header["header_param"]
        )

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
                "benchmark.name": ["uperf"],
                "benchmark.primary_metric": ["Gb_sec"],
                "benchmark.protocol": ["tcp"],
                "benchmark.test_type": ["stream"],
                "benchmark.uid": ["benchmark_name:uperf-controller_host:host.name.com"],
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
                "run.config": ["npalaska"],
                "run.controller": ["host.name.com"],
                "run.id": ["f3a37c9891a78886639e3bc00e3c5c4e"],
                "run.name": ["uperf_npalaska_2021.07.14T15.30.22"],
                "run.script": ["uperf"],
                "sample.client_hostname": ["127.0.0.1", "all"],
                "sample.measurement_title.raw": ["Gb_sec"],
                "sample.measurement_type": ["throughput"],
                "sample.name": ["sample1", "sample2", "sample3", "sample4", "sample5"],
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


class TestSampleValues(Commons):
    """
    Unit testing for IterationSamplesRowse class.
    In a web service context, we access class functions mostly via the
    Flask test client rather than trying to directly invoke the class
    constructor and `post` service.
    """

    SCROLL_ID = "random_scroll_id_string_1=="

    @pytest.fixture(autouse=True)
    def _setup(self, client):
        super()._setup(
            cls_obj=SampleValues(client.config, client.logger),
            pbench_endpoint="/datasets/values/iterations",
            elastic_endpoint="/_search",
            payload={"run_id": "random_md5_string1"},
            index_from_metadata="result-data-sample",
        )

    @pytest.mark.parametrize("filters", ({"sample.name": "sample1"}, {}, None))
    def test_rows_query_without_scroll(
        self,
        server_config,
        query_api,
        pbench_token,
        build_auth_header,
        find_template,
        provide_metadata,
        filters,
    ):
        response_payload = {
            "_scroll_id": TestSampleValues.SCROLL_ID,
            "took": 14,
            "timed_out": "false",
            "_shards": {"total": 5, "successful": 5, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "max_score": "null",
                "hits": [
                    {
                        "_index": "staging-pbench.v5.result-data-sample.2021-03-03",
                        "_type": "_doc",
                        "_id": "624a30066072f836d4cd501174d23f35",
                        "_score": 0.0,
                        "_source": {
                            "@timestamp": "2021-03-03T01:58:58.712889",
                            "run": {
                                "id": "58bed61de1fd6ce57d682c320c506c4a",
                                "controller": "controller.name.com",
                                "name": "fio_rw_2021.03.03T01.58.34",
                                "script": "fio",
                                "date": "2021-03-03T01:58:34",
                                "start": "2021-03-03T01:58:57.712889",
                                "end": "2021-03-03T02:01:46.382422",
                                "config": "rw",
                                "user": "ndk",
                            },
                            "iteration": {"name": "1-rw-4KiB", "number": 1},
                            "benchmark": {
                                "bs": "4k",
                                "clocksource": "gettimeofday",
                                "direct": "0",
                                "filename": "/home/pbench/tmp/foo,/home/pbench/tmp/foo,/home/pbench/tmp/foo,/home/pbench/tmp/foo",
                                "iodepth": "32",
                                "ioengine": "libaio",
                                "log_avg_msec": "1000",
                                "log_hist_msec": "10000",
                                "max_stddevpct": 5,
                                "numjobs": "4,4,4,4",
                                "primary_metric": "iops_sec",
                                "ramp_time": "5",
                                "runtime": "10",
                                "rw": "rw,rw,rw,rw",
                                "size": "4096M,4096M,4096M,4096M",
                                "sync": "0",
                                "time_based": "1",
                                "uid": "benchmark_name:fio-controller_host:controller.name.com",
                                "name": "fio",
                                "uid_tmpl": "benchmark_name:%benchmark_name%-controller_host:%controller_host%",
                            },
                            "sample": {
                                "client_hostname": "localhost-1",
                                "closest_sample": 1,
                                "description": "Average completion latency per I/O operation",
                                "mean": 759737976.333333,
                                "role": "client",
                                "stddev": 0,
                                "stddevpct": 0,
                                "uid": "client_hostname:localhost-1",
                                "measurement_type": "latency",
                                "measurement_idx": 3,
                                "measurement_title": "clat",
                                "uid_tmpl": "client_hostname:%client_hostname%",
                                "@idx": 0,
                                "name": "sample1",
                                "start": "2021-03-03T01:58:58.712889",
                                "end": "2021-03-03T01:59:07.725889",
                            },
                            "@timestamp_original": "1000",
                            "@generated-by": "cce1f6d53404b43e5a006c8e6d88e1e0",
                        },
                    },
                    {
                        "_index": "staging-pbench.v5.result-data-sample.2021-03-03",
                        "_type": "_doc",
                        "_id": "20c70f03ff717b82e9f419e8d972b748",
                        "_score": 0.0,
                        "_source": {
                            "@timestamp": "2021-03-03T01:58:58.712889",
                            "run": {
                                "id": "58bed61de1fd6ce57d682c320c506c4a",
                                "controller": "controller.name.com",
                                "name": "fio_rw_2021.03.03T01.58.34",
                                "script": "fio",
                                "date": "2021-03-03T01:58:34",
                                "start": "2021-03-03T01:58:57.712889",
                                "end": "2021-03-03T02:01:46.382422",
                                "config": "rw",
                                "user": "ndk",
                            },
                            "iteration": {"name": "1-rw-4KiB", "number": 1},
                            "benchmark": {
                                "bs": "4k",
                                "clocksource": "gettimeofday",
                                "direct": "0",
                                "filename": "/home/pbench/tmp/foo,/home/pbench/tmp/foo,/home/pbench/tmp/foo,/home/pbench/tmp/foo",
                                "iodepth": "32",
                                "ioengine": "libaio",
                                "log_avg_msec": "1000",
                                "log_hist_msec": "10000",
                                "max_stddevpct": 5,
                                "numjobs": "4,4,4,4",
                                "primary_metric": "iops_sec",
                                "ramp_time": "5",
                                "runtime": "10",
                                "rw": "rw,rw,rw,rw",
                                "size": "4096M,4096M,4096M,4096M",
                                "sync": "0",
                                "time_based": "1",
                                "uid": "benchmark_name:fio-controller_host:controller.name.com",
                                "name": "fio",
                                "uid_tmpl": "benchmark_name:%benchmark_name%-controller_host:%controller_host%",
                            },
                            "sample": {
                                "client_hostname": "localhost-4",
                                "closest_sample": 1,
                                "description": "Average completion latency per I/O operation",
                                "mean": 761676162.46875,
                                "role": "client",
                                "stddev": 0,
                                "stddevpct": 0,
                                "uid": "client_hostname:localhost-4",
                                "measurement_type": "latency",
                                "measurement_idx": 0,
                                "measurement_title": "clat",
                                "uid_tmpl": "client_hostname:%client_hostname%",
                                "@idx": 0,
                                "name": "sample1",
                                "start": "2021-03-03T01:58:58.712889",
                                "end": "2021-03-03T01:59:07.725889",
                            },
                            "@timestamp_original": "1000",
                            "@generated-by": "cce1f6d53404b43e5a006c8e6d88e1e0",
                        },
                    },
                ],
            },
        }
        index = self.build_index_from_metadata()

        auth_json = {"user": "drb", "access": "private"}
        expected_status = self.get_expected_status(
            auth_json, build_auth_header["header_param"]
        )
        if filters is not None:
            self.payload["filters"] = filters

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
            assert response.json == {
                "results": [hit["_source"] for hit in response_payload["hits"]["hits"]]
            }

    @pytest.mark.parametrize("filters", ({"sample.name": "sample1"}, {}, None))
    def test_scroll_id_return(
        self,
        server_config,
        query_api,
        pbench_token,
        build_auth_header,
        find_template,
        provide_metadata,
        filters,
    ):
        response_payload = {
            "_scroll_id": TestSampleValues.SCROLL_ID,
            "took": 14,
            "timed_out": "false",
            "_shards": {"total": 5, "successful": 5, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 10001, "relation": "eq"},
                "max_score": "null",
                "hits": [
                    {
                        "_index": "staging-pbench.v5.result-data-sample.2021-03-03",
                        "_type": "_doc",
                        "_id": "624a30066072f836d4cd501174d23f35",
                        "_score": 0.0,
                        "_source": {},
                    },
                ]
                + (
                    [
                        {
                            "_index": "staging-pbench.v5.result-data-sample.2021-03-03",
                            "_type": "_doc",
                            "_id": "20c70f03ff717b82e9f419e8d972b748",
                            "_score": 0.0,
                            "_source": {},
                        }
                    ]
                    * 9999
                ),
            },
        }
        index = self.build_index_from_metadata()

        auth_json = {"user": "drb", "access": "private"}
        expected_status = self.get_expected_status(
            auth_json, build_auth_header["header_param"]
        )
        if filters is not None:
            self.payload["filters"] = filters

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
            assert TestSampleValues.SCROLL_ID == res_json["scroll_id"]

    def test_rows_query_with_scroll_id(
        self,
        server_config,
        query_api,
        pbench_token,
        build_auth_header,
        find_template,
        provide_metadata,
    ):
        self.payload["scroll_id"] = TestSampleValues.SCROLL_ID

        response_payload = {
            "_scroll_id": "random_scroll_id_string_2==",
            "took": 3,
            "timed_out": "false",
            "_shards": {"total": 5, "successful": 5, "skipped": 0, "failed": 0},
            "hits": {
                "total": {"value": 10001, "relation": "eq"},
                "max_score": "null",
                "hits": [
                    {
                        "_index": "staging-pbench.v5.result-data-sample.2020-09-03",
                        "_type": "_doc",
                        "_id": "84602c1c6417260ee72d92eca68ecca3",
                        "_score": "null",
                        "_source": {
                            "@timestamp": "2020-09-03T01:58:58.712889",
                            "run": {
                                "id": "58bed61de1fd6ce57d682c320c506c4a",
                                "controller": "controller.name.com",
                                "name": "fio_rw_2020.09.03T01.58.34",
                                "script": "fio",
                                "date": "2020-09-03T01:58:34",
                                "start": "2020-09-03T01:58:57.712889",
                                "end": "2020-09-03T02:01:46.382422",
                                "config": "rw",
                                "user": "ndk",
                            },
                            "iteration": {"name": "1-rw-4KiB", "number": 1},
                            "benchmark": {
                                "bs": "4k",
                                "clocksource": "gettimeofday",
                                "direct": "0",
                                "filename": "/home/pbench/tmp/foo,/home/pbench/tmp/foo,/home/pbench/tmp/foo,/home/pbench/tmp/foo",
                                "iodepth": "32",
                                "ioengine": "libaio",
                                "log_avg_msec": "1000",
                                "log_hist_msec": "10000",
                                "max_stddevpct": 5,
                                "numjobs": "4,4,4,4",
                                "primary_metric": "iops_sec",
                                "ramp_time": "5",
                                "runtime": "10",
                                "rw": "rw,rw,rw,rw",
                                "size": "4096M,4096M,4096M,4096M",
                                "sync": "0",
                                "time_based": "1",
                                "uid": "benchmark_name:fio-controller_host:controller.name.com",
                                "name": "fio",
                                "uid_tmpl": "benchmark_name:%benchmark_name%-controller_host:%controller_host%",
                            },
                            "sample": {
                                "client_hostname": "localhost-2",
                                "closest_sample": 1,
                                "description": "Average submission latency per I/O operation",
                                "mean": 1857025.80208333,
                                "role": "client",
                                "stddev": 0,
                                "stddevpct": 0,
                                "uid": "client_hostname:localhost-2",
                                "measurement_type": "latency",
                                "measurement_idx": 2,
                                "measurement_title": "slat",
                                "uid_tmpl": "client_hostname:%client_hostname%",
                                "@idx": 0,
                                "name": "sample1",
                                "start": "2020-09-03T01:58:58.712889",
                                "end": "2020-09-03T01:59:07.725889",
                            },
                            "@timestamp_original": "1000",
                            "@generated-by": "cce1f6d53404b43e5a006c8e6d88e1e0",
                        },
                        "sort": [1],
                    }
                ],
            },
        }

        auth_json = {"user": "drb", "access": "private"}
        expected_status = self.get_expected_status(
            auth_json, build_auth_header["header_param"]
        )

        response = query_api(
            self.pbench_endpoint,
            f"{self.elastic_endpoint}/scroll",
            self.payload,
            "",
            expected_status,
            json=response_payload,
            status=HTTPStatus.OK,
            headers=build_auth_header["header"],
        )

        if expected_status == HTTPStatus.OK:
            assert response.json == {
                "results": [hit["_source"] for hit in response_payload["hits"]["hits"]]
            }

    def test_get_index(self, attach_dataset, provide_metadata):
        drb = Dataset.query(name="drb")
        indices = self.cls_obj.get_index(drb, self.index_from_metadata)
        assert indices == "unit-test.v5.result-data-sample.2020-08"

    def test_exceptions_on_get_index(self, attach_dataset):
        test = Dataset.query(name="test")

        # When server index_map is None we expect 500
        with pytest.raises(InternalServerError) as exc:
            self.cls_obj.get_index(test, self.index_from_metadata)
        assert exc.value.code == HTTPStatus.INTERNAL_SERVER_ERROR

        Metadata.setvalue(
            dataset=test,
            key=Metadata.INDEX_MAP,
            value={"unit-test.v6.run-data.2020-08": ["random_md5_string1"]},
        )

        # When server index_map doesn't have mappings for result-data-sample
        # documents we expect the indices to an empty string
        assert self.cls_obj.get_index(test, self.index_from_metadata) == ""
