#!/usr/bin/env python3

import json
import multiprocessing
import os
import requests
import sys
import time

from collections import OrderedDict
from datetime import datetime
from dateutil import rrule
from dateutil.relativedelta import relativedelta

from elasticsearch1 import Elasticsearch
from elasticsearch1.helpers import scan


def _month_gen(now: datetime):
    """Generate YYYY-MM stings from all the months, inclusively, between the
    given start and end dates.
    """
    start = now - relativedelta(years=1)
    first_month = start.replace(day=1)
    last_month = now + relativedelta(day=31)
    for m in rrule.rrule(rrule.MONTHLY, dtstart=first_month, until=last_month):
        yield f"{m.year:04}-{m.month:02}"


def result_index_gen(month_gen):
    """Yield all the result index patterns for each month yielded from the given
    generator.
    """
    for month in month_gen:
        yield f"dsa-pbench.v4.result-data.{month}-*"


def run_index_gen(month_gen):
    """Yield all the run data index patterns for each month yielded from the given
    generator.
    """
    for month in month_gen:
        yield f"dsa-pbench.v4.run.{month}"


def es_data_gen(es, index, doc_type):
    """Yield documents where the `run.script` field is "fio" for the given index
    and document type.
    """
    query = {"query": {"query_string": {"query": "run.script:fio"}}}

    for doc in scan(
        es,
        query=query,
        index=index,
        doc_type=doc_type,
        scroll="1d",
        request_timeout=3600,  # to prevent timeout errors (3600 is arbitrary)
    ):
        yield doc


def pbench_runs_gen(es, month_gen):
    """Yield all the pbench run documents using the given month generator."""
    for run_index in run_index_gen(month_gen):
        for doc in es_data_gen(es, run_index, "pbench-run"):
            yield doc


def pbench_result_data_samples_gen(es, month_gen):
    """Yield all the pbench result data sample documents using the given month
    generator.
    """
    for result_index in result_index_gen(month_gen):
        for doc in es_data_gen(es, result_index, "pbench-result-data-sample"):
            yield doc


def load_pbench_runs(es, now: datetime):
    """Load all the pbench run data, sub-setting to contain only the fields we
    require.

    We also ignore any pbench run without a `controller_dir` field or without
    a `sosreports` field.

    A few statistics about the processing is printed to stdout.

    Returns a dictionary containing the processed pbench run documents
    """
    pbench_runs = dict()

    recs = 0
    missing_ctrl_dir = 0
    missing_sos = 0
    sos_not_two = 0
    accepted = 0

    for _source in pbench_runs_gen(es, _month_gen(now)):
        recs += 1

        run = _source["_source"]
        run_id = run["@metadata"]["md5"]
        if "controller_dir" not in run["@metadata"]:
            missing_ctrl_dir += 1
            print(f"pbench run with no controller_dir: {run_id}")
            continue

        if "sosreports" not in run:
            missing_sos += 1
            continue

        if len(run["sosreports"]) != 2:
            sos_not_two += 1
            continue

        first = run["sosreports"][0]
        second = run["sosreports"][1]
        if first["hostname-f"] != second["hostname-f"]:
            print(f"pbench run with sosreports from different hosts: {run_id}")
            continue

        accepted += 1

        run_index = _source["_index"]

        sosreports = dict()
        # FIXME: Should I remove the forloop here after the above change?
        for sosreport in run["sosreports"]:
            sosreports[os.path.split(sosreport["name"])[1]] = {
                "hostname-s": sosreport["hostname-s"],
                "hostname-f": sosreport["hostname-f"],
                "time": sosreport["name"].split("/")[2],
                "inet": [nic["ipaddr"] for nic in sosreport["inet"]],
                # FIXME: Key Error on inet6
                # "inet6": [nic["ipaddr"] for nic in sosreport["inet6"]],
            }

        pbench_runs[run_id] = dict(
            run_id=run_id,
            run_index=run_index,
            controller_dir=run["@metadata"]["controller_dir"],
            sosreports=sosreports,
        )

    print(
        f"Stats for pbench runs: accepted {accepted:n} records of"
        f" {recs:n}, missing 'controller_dir' field {missing_ctrl_dir:n},"
        f" missing 'sosreports' field {missing_sos:n}",
        f" 'sosreports' not equal to two for single clients {sos_not_two:n}",
        flush=True,
    )

    return pbench_runs


# extract list of clients from the URL
def extract_clients(results_meta, es):
    run_index = results_meta["run_index"]
    parent_id = results_meta["run.id"]
    iter_name = results_meta["iteration.name"]
    sample_name = results_meta["sample.name"]
    parent_dir_name = f"/{iter_name}/{sample_name}/clients"
    query = {
        "query": {
            "query_string": {
                "query": f'_parent:"{parent_id}"'
                f' AND ancestor_path_elements:"{iter_name}"'
                f' AND ancestor_path_elements:"{sample_name}"'
                f" AND ancestor_path_elements:clients"
            }
        }
    }

    client_names_raw = []
    for doc in scan(
        es,
        query=query,
        index=run_index,
        doc_type="pbench-run-toc-entry",
        scroll="1m",
        request_timeout=3600,  # to prevent timeout errors (3600 is arbitrary)
    ):
        src = doc["_source"]
        if src["parent"] == parent_dir_name:
            client_names_raw.append(src["name"])
    # FIXME: if we have an empty list, do we still want to use those results?
    return list(set(client_names_raw))


# extract host and disk names from fio-result.txt
def extract_fio_result(results_meta, incoming_url, session):
    url = (
        incoming_url
        + results_meta["controller_dir"]
        + "/"
        + results_meta["run.name"]
        + "/"
        + results_meta["iteration.name"]
        + "/"
        + results_meta["sample.name"]
        + "/"
        + "fio-result.txt"
    )

    # check if the page is accessible
    response = session.get(url, allow_redirects=True)
    if response.status_code != 200:  # successful
        # FIXME: are these results we still want?
        return ([], [])

    try:
        document = response.json()
    except ValueError:
        # print("Response content is not valid JSON")
        # print(url)
        # print(response.content)
        # FIXME: are these results we still want?
        return ([], [])

    try:
        disk_util = document["disk_util"]
    except KeyError:
        disknames = []
    else:
        disknames = [disk["name"] for disk in disk_util if "name" in disk]

    try:
        client_stats = document["client_stats"]
    except KeyError:
        hostnames = []
    else:
        hostnames = list(
            set([host["hostname"] for host in client_stats if "hostname" in host])
        )

    return (disknames, hostnames)


def transform_result(source, pbench_runs, results_seen, stats):
    """Transform the raw result data sample document to a stripped down version,
    augmented with pbench run data.
    """
    result_id = source["_id"]
    assert result_id not in results_seen, f"Result ID {result_id} repeated"
    results_seen[result_id] = True

    try:
        index = source["_source"]
        run = index["run"]
        run_id = run["id"]
        run_name = run["name"]
        iter_name = index["iteration"]["name"]
        sample = index["sample"]
        sample_name = sample["name"]
        sample_m_type = sample["measurement_type"]
        sample_m_title = sample["measurement_title"]
        sample_m_idx = sample["measurement_idx"]
    except KeyError as exc:
        print(
            # f"ERROR - {filename}, {exc}, {json.dumps(index)}", file=sys.stderr,
            f"ERROR - {exc}, {json.dumps(index)}",
            file=sys.stderr,
        )
        stats["errors"] += 1
        return None

    try:
        pbench_run = pbench_runs[run_id]
    except KeyError:
        # print(
        #    f"*** Result without a run: {run_id}/{run_name}/{iter_name}"
        #    f"/{sample_name}/{sample_m_type}/{sample_m_title}"
        #    f"/{sample_m_idx}",
        #    flush=True,
        # )
        stats["missing_runs"] += 1
        return None

    if "mean" not in sample:
        # run_ctrl = pbench_run["controller_dir"]
        # print(
        #    f"No 'mean' in {run_ctrl}/{run_name}/{iter_name}"
        #    f"/{sample_name}/{sample_m_type}/{sample_m_title}"
        #    f"/{sample_m_idx}",
        #    flush=True,
        # )
        stats["missing_mean"] += 1
        return None

    if sample["client_hostname"] == "all":
        stats["aggregate_result"] += 1
        return None

    # The following field names are required
    try:
        benchmark = index["benchmark"]
        result = OrderedDict()
        result.update(
            [
                ("run.id", run_id),
                ("iteration.name", iter_name),
                ("sample.name", sample_name),
                ("run.name", run_name),
                ("benchmark.bs", benchmark["bs"]),
                ("benchmark.direct", benchmark["direct"]),
                ("benchmark.ioengine", benchmark["ioengine"]),
                ("benchmark.max_stddevpct", benchmark["max_stddevpct"]),
                ("benchmark.primary_metric", benchmark["primary_metric"]),
                ("benchmark.rw", ", ".join(set((benchmark["rw"].split(","))))),
                ("sample.client_hostname", sample["client_hostname"]),
                ("sample.measurement_type", sample_m_type),
                ("sample.measurement_title", sample_m_title),
                ("sample.measurement_idx", sample_m_idx),
                ("sample.mean", sample["mean"]),
                ("sample.stddev", sample["stddev"]),
                ("sample.stddevpct", sample["stddevpct"]),
            ]
        )
    except KeyError as exc:
        print(
            # f"ERROR - {filename}, {exc}, {json.dumps(index)}", file=sys.stderr,
            f"ERROR - {exc}, {json.dumps(index)}",
            file=sys.stderr,
        )
        stats["errors"] += 1
        return None

    stats["mean"] += 1

    result["run_index"] = pbench_run["run_index"]
    result["controller_dir"] = pbench_run["controller_dir"]
    result["sosreports"] = pbench_run["sosreports"]

    # optional workload parameters accounting for defaults if not found

    result["benchmark.filename"] = sentence_setify(
        benchmark.get("filename", "/tmp/fio")
    )
    result["benchmark.iodepth"] = benchmark.get("iodepth", "32")
    result["benchmark.size"] = sentence_setify(benchmark.get("size", "4096M"))
    result["benchmark.numjobs"] = sentence_setify(benchmark.get("numjobs", "1"))
    result["benchmark.ramp_time"] = benchmark.get("ramp_time", "none")
    result["benchmark.runtime"] = benchmark.get("runtime", "none")
    result["benchmark.sync"] = benchmark.get("sync", "none")
    result["benchmark.time_based"] = benchmark.get("time_based", "none")

    return result


def sentence_setify(sentence: str) -> str:
    """Splits input by ", " gets rid of duplicates and rejoins unique
    items into original format. Effectively removes duplicates in input.
    """
    return ", ".join(set((sentence.split(", "))))


def process_results(es, now, session, incoming_url, pool, pbench_runs, stats):
    """Intermediate generator for handling the fetching of the client names, disk
    names, and host names.

    """
    stats["total_recs"] = 0
    stats["missing_mean"] = 0
    stats["missing_runs"] = 0
    stats["aggregate_result"] = 0
    stats["multiple_clients"] = 0
    stats["no_clients"] = 0
    stats["errors"] = 0
    stats["mean"] = 0

    results_seen = dict()
    clientnames_map = dict()
    diskhost_map = dict()

    for _source in pbench_result_data_samples_gen(es, _month_gen(now)):
        stats["total_recs"] += 1
        result = transform_result(_source, pbench_runs, results_seen, stats)
        if result is None:
            continue

        # Add host and disk names in the data here
        key = f'{result["run.id"]}/{result["iteration.name"]}'
        try:
            disknames, hostnames = diskhost_map[key]
        except KeyError:
            print(f"{key} / fio-result.txt", flush=True)
            disknames, hostnames = extract_fio_result(result, incoming_url, session)
            diskhost_map[key] = (disknames, hostnames)
        result["disknames"] = disknames
        result["hostnames"] = hostnames

        # Add client names here
        key = result["run.id"]
        try:
            clientnames = clientnames_map[key]
        except KeyError:
            print(f"{key} / client names", flush=True)
            clientnames = extract_clients(result, es)
            clientnames_map[key] = clientnames

        # Ignore result if 0 or more than 1 client names
        if not clientnames:
            stats["no_clients"] += 1
            continue

        if len(clientnames) > 1:
            stats["multiple_clients"] += 1
            continue

        result["clientnames"] = clientnames

        yield result


def main(args):
    # Number of CPUs to use (where 0 = n CPUs)
    concurrency = int(args[1])

    es_host = args[2]
    es_port = args[3]

    # URL prefix to fetch unpacked data
    url_prefix = args[4]
    incoming_url = f"{url_prefix}/incoming/"

    # If requested, profile memory usage
    try:
        profile_arg = int(args[5])
    except (IndexError, ValueError):
        profile = False
    else:
        profile = profile_arg != 0

    if profile:
        from guppy import hpy

        memprof = hpy()
    else:
        memprof = None

    if memprof:
        print(f"Initial memory profile ... {memprof.heap()}", flush=True)

    # We create the multiprocessing pool first to avoid forking a sub-process
    # with lots of memory allocated.
    ncpus = multiprocessing.cpu_count() - 1 if concurrency == 0 else concurrency
    pool = multiprocessing.Pool(ncpus) if ncpus != 1 else None

    es = Elasticsearch(
        [f"{es_host}:{es_port}"], timeout=60
    )  # to prevent read timeout errors (60 is arbitrary)

    session = requests.Session()
    ua = session.headers["User-Agent"]
    session.headers.update({"User-Agent": f"{ua} -- merge_sos_and_perf_parallel"})

    scan_start = time.time()
    now = datetime.utcfromtimestamp(scan_start)

    pbench_runs = load_pbench_runs(es, now)

    result_cnt = 0
    stats = dict()

    with open("sosreport_fio.txt", "w") as log, open("pbench_fio.json", "w") as outfile:
        generator = process_results(
            es, now, session, incoming_url, pool, pbench_runs, stats
        )
        for result in generator:
            result_cnt += 1
            for sos in result["sosreports"].keys():
                log.write("{}\n".format(sos))
            log.flush()
            outfile.write(json.dumps(result))
            outfile.write("\n")
            outfile.flush()

    scan_end = time.time()
    duration = scan_end - scan_start

    print(f"final number of records: {result_cnt:n}", flush=True)
    print(json.dumps(stats, indent=4), flush=True)
    print(f"--- merging run and result data took {duration:0.2f} seconds", flush=True)

    if memprof:
        print(
            f"Final memory profile ... {memprof.heap()}",
            flush=True,
        )

    return 0


# point of entry
if __name__ == "__main__":
    status = main(sys.argv)
