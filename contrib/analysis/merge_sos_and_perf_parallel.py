#!/usr/bin/env python3

import json
import multiprocessing
import os
import requests
import sys
import time

from elasticsearch1 import Elasticsearch
from elasticsearch1.helpers import scan


def load_pbench_runs(dirname, memprof):
    """Load all the pbench run data, sub-setting to contain only the fields we
    require.

    We also ignore any pbench run without a `controller_dir` field or without
    a `sosreports` field.

    A few statistics about the processing is printed to stdout.

    Returns a dictionary containing the processed pbench run documents
    """
    if memprof:
        print(
            f"Memory profile before ingesting run data documents ... {memprof.heap()}",
            flush=True,
        )

    total_recs = 0
    total_missing_ctrl_dir = 0
    total_missing_sos = 0
    total_accepted = 0

    pbench_runs = dict()

    for filename in os.listdir(dirname):
        if not filename.endswith(".json"):  # code
            continue
        if not filename.startswith("pbench_run_data_fio_"):
            continue

        print(f"Loading {filename}...", flush=True)
        with open(dirname + "/" + filename) as f:  # releases the handler itself
            data = json.load(f)

        print(f"Processing {filename}...", flush=True)
        recs = 0
        missing_ctrl_dir = 0
        missing_sos = 0
        accepted = 0
        for _source in data["hits"]["hits"]:
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

            accepted += 1

            run_index = _source["_index"]

            sosreports = dict()
            for sosreport in run["sosreports"]:
                sosreports[os.path.split(sosreport["name"])[1]] = {
                    "hostname-s": sosreport["hostname-s"],
                    "hostname-f": sosreport["hostname-f"],
                    "time": sosreport["name"].split("/")[2],
                }

            pbench_runs[run_id] = dict(
                run_id=run_id,
                run_index=run_index,
                controller_dir=run["@metadata"]["controller_dir"],
                sosreports=sosreports,
            )
        print(
            f"Stats for {filename}: accepted {accepted:n} records of"
            f" {recs:n}, missing 'controller_dir' field {missing_ctrl_dir:n},"
            f" missing 'sosreports' field {missing_sos:n}",
            flush=True,
        )

        total_recs += recs
        total_accepted += accepted
        total_missing_ctrl_dir += missing_ctrl_dir
        total_missing_sos += missing_sos

    print(
        f"\nPbench Run Totals: accepted {total_accepted:n} records of {total_recs:n},"
        f"\n\tmissing 'controller_dir' field: {total_missing_ctrl_dir:n}"
        f"\n\tmissing 'sosreports' field: {total_missing_sos:n}",
        flush=True,
    )

    if memprof:
        print(
            f"Memory profile after ingesting run data documents ... {memprof.heap()}",
            flush=True,
        )
    return pbench_runs


# extract pbench run metadata and workload
# information from indexed pbench results data
def extract_pbench_results(dirname, memprof):
    # counts
    total_recs = 0
    mean = 0
    # counts

    if memprof:
        print(f"Initial memory profile ... {memprof.heap()}", flush=True)

    # The result sample documents by result ID
    results = dict()
    # Maps result ID to run ID
    result_to_run = dict()
    # Maps run ID to list of result IDs
    run_to_results = dict()

    for filename in os.listdir(dirname):
        if not filename.endswith(".json"):  # code
            continue
        if not filename.startswith("pbench_result_data_fio_"):
            continue

        print(f"Loading {filename}...", flush=True)
        with open(dirname + "/" + filename) as f:  # releases the handler itself
            data = json.load(f)

        print(f"Processing {filename}...", flush=True)
        for source in data["hits"]["hits"]:
            result_id = source["_id"]
            assert result_id not in results.keys(), f"Result ID {result_id} repeated"

            # counts
            total_recs += 1

            index = source["_source"]
            run = index["run"]
            run_ctrl = run["controller"]
            run_name = run["name"]
            iter_name = index["iteration"]["name"]
            sample = index["sample"]
            sample_name = sample["name"]
            sample_m_type = sample["measurement_type"]
            sample_m_title = sample["measurement_title"]
            sample_m_idx = sample["measurement_idx"]

            if "mean" not in sample:
                print(
                    f"No 'mean' in {run_ctrl}/{run_name}/{iter_name}"
                    f"/{sample_name}/{sample_m_type}/{sample_m_title}"
                    f"/{sample_m_idx}",
                    flush=True,
                )
                continue

            # The following field names are required
            try:
                benchmark = index["benchmark"]
                run_id = run["id"]
                result = {
                    "run.id": run_id,
                    "run.name": run_name,
                    "iteration.name": iter_name,
                    "benchmark.bs": benchmark["bs"],
                    "benchmark.direct": benchmark["direct"],
                    "benchmark.ioengine": benchmark["ioengine"],
                    "benchmark.max_stddevpct": benchmark["max_stddevpct"],
                    "benchmark.primary_metric": benchmark["primary_metric"],
                    "benchmark.rw": ", ".join(set((benchmark["rw"].split(",")))),
                    "sample.name": sample_name,
                    "sample.client_hostname": sample["client_hostname"],
                    "sample.measurement_type": sample_m_type,
                    "sample.measurement_title": sample_m_title,
                    "sample.measurement_idx": sample_m_idx,
                    "sample.mean": sample["mean"],
                    "sample.stddev": sample["stddev"],
                    "sample.stddevpct": sample["stddevpct"],
                }
            except KeyError as exc:
                print(
                    f"ERROR - {filename}, {exc}, {json.dumps(index)}", file=sys.stderr,
                )
                continue

            # Only count the mean if we have all the required fields.
            mean += 1

            # optional workload parameters
            try:
                result["benchmark.filename"] = ", ".join(
                    set((benchmark["filename"].split(",")))
                )
            except KeyError:
                result["benchmark.filename"] = "/tmp/fio"
            try:
                result["benchmark.iodepth"] = benchmark["iodepth"]
            except KeyError:
                result["benchmark.iodepth"] = "32"
            try:
                result["benchmark.size"] = ", ".join(
                    set((benchmark["size"].split(",")))
                )
            except KeyError:
                result["benchmark.size"] = "4096M"
            try:
                result["benchmark.numjobs"] = ", ".join(
                    set((benchmark["numjobs"].split(",")))
                )
            except KeyError:
                result["benchmark.numjobs"] = "1"
            try:
                result["benchmark.ramp_time"] = benchmark["ramp_time"]
            except KeyError:
                result["benchmark.ramp_time"] = "none"
            try:
                result["benchmark.runtime"] = benchmark["runtime"]
            except KeyError:
                result["benchmark.runtime"] = "none"
            try:
                result["benchmark.sync"] = benchmark["sync"]
            except KeyError:
                result["benchmark.sync"] = "none"
            try:
                result["benchmark.time_based"] = benchmark["time_based"]
            except KeyError:
                result["benchmark.time_based"] = "none"

            results[result_id] = result
            result_to_run[result_id] = run_id
            if run_id not in run_to_results:
                run_to_results[run_id] = []
            run_to_results[run_id].append(result_id)

    print("total pbench result records: " + str(total_recs))
    print("records with mean available: " + str(mean))

    if memprof:
        print(
            f"Memory profile after ingesting result data sample documents ... {memprof.heap()}",
            flush=True,
        )

    return results, result_to_run, run_to_results


# extract controller directory and sosreports'
# names associated with each pbench run and
# merge it with the result data
def extract_pbench_runs(
    dirname,
    es_host,
    es_port,
    results,
    result_to_run,
    run_to_results,
    incoming_url,
    pool,
    memprof,
):
    if memprof:
        print(
            f"Memory profile before ingesting run data documents ... {memprof.heap()}",
            flush=True,
        )

    # counts
    total_recs = 0
    controller_dir = 0
    sos = 0
    run_wo_res = 0
    cloud = 0
    # counts

    # to store results that have corresponding run data
    pbench = dict()

    # stores output for all the results with complete data
    result_list = []

    # tells if runs has associated result data
    valid_run = False

    session = requests.Session()
    ua = session.headers["User-Agent"]
    session.headers.update({"User-Agent": f"{ua} -- merge_sos_and_perf_parallel"})

    es = Elasticsearch([f"{es_host}:{es_port}"])

    for filename in os.listdir(dirname):
        if not filename.endswith(".json"):  # code
            continue
        if not filename.startswith("pbench_run_data_fio_"):
            continue

        print(f"Loading {filename}...", flush=True)
        with open(dirname + "/" + filename) as f:  # releases the handler itself
            data = json.load(f)

        print(f"Processing {filename}...", flush=True)
        for source in data["hits"]["hits"]:

            # counts
            total_recs = total_recs + 1
            if "controller_dir" in source["_source"]["@metadata"]:
                controller_dir = controller_dir + 1
                if source["_source"]["@metadata"]["controller_dir"].startswith("EC2::"):
                    cloud = cloud + 1
            else:
                print(
                    "pbench run with no controller_dir: "
                    + source["_source"]["@metadata"]["md5"]
                )
                continue

            if source["_source"]["@metadata"]["md5"] not in run_to_results:
                run_wo_res = run_wo_res + 1
                print(f"*** run without results: {source['_source']['run']['name']}")
                valid_run = False
            else:
                valid_run = True

            if "sosreports" in source["_source"]:
                sos = sos + 1
            # counts

            if valid_run and "sosreports" in source["_source"]:
                if pool:
                    result_list.append(
                        pool.apply_async(
                            extract_run_metadata,
                            args=(
                                results,
                                result_to_run,
                                run_to_results,
                                source["_source"],
                                source["_index"],
                                incoming_url,
                                session,
                                es,
                            ),
                        )
                    )
                else:
                    pbench.update(
                        extract_run_metadata(
                            results,
                            result_to_run,
                            run_to_results,
                            source["_source"],
                            source["_index"],
                            incoming_url,
                            session,
                            es,
                        )
                    )

        if pool:
            pool.close()  # no more parallel work to submit
            pool.join()  # wait for the worker processes to terminate

            for res in result_list:
                record = res.get()
                if record:
                    pbench.update(record)

    print("total pbench run records: " + str(total_recs))
    print("records with controller_dir: " + str(controller_dir))
    print("records with sosreports: " + str(sos))
    print("runs without any pbench results: " + str(run_wo_res))
    print("records with complete info: " + str(total_recs - run_wo_res))
    print("cloud: " + str(cloud))
    print("noncloud: " + str(controller_dir - cloud))

    return pbench


# extract controller directory and sosreports'
# names associated with each pbench run
def extract_run_metadata(
    results,
    result_to_run,
    run_to_results,
    run_record,
    run_index,
    incoming_url,
    session,
    es,
):
    # print (f"Entered run metadata: {run_record['run']['name']}")

    temp = dict()

    # since clientnames are common to all iterations
    clientnames = None

    # since disknames and hostnames are common to all samples
    current_iter_name = None

    # since sosreports are common to all results per run
    sosreports = None

    for result_id in run_to_results[run_record["@metadata"]["md5"]]:
        result = results[result_id]
        result["run_index"] = run_index
        result["controller_dir"] = run_record["@metadata"]["controller_dir"]

        if sosreports is None:
            sosreports = dict()
            for sosreport in run_record["sosreports"]:
                sosreports[os.path.split(sosreport["name"])[1]] = {
                    "hostname-s": sosreport["hostname-s"],
                    "hostname-f": sosreport["hostname-f"],
                    "time": sosreport["name"].split("/")[2],
                }
        result["sosreports"] = sosreports

        # add host and disk names in the data here
        iter_name = result["iteration.name"]
        if current_iter_name != iter_name:
            # print ("Before fio")
            disknames, hostnames = extract_fio_result(result, incoming_url, session)
            current_iter_name = iter_name
        result["disknames"] = disknames
        result["hostnames"] = hostnames

        # add client names here
        if clientnames is None:
            # print ("Before clients")
            clientnames = extract_clients(result, es)
        result["clientnames"] = clientnames

        temp[result_id] = result

    return temp


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
        es, query=query, index=run_index, doc_type="pbench-run-toc-entry", scroll="1m",
    ):
        src = doc["_source"]
        assert (
            src["parent"] == parent_dir_name
        ), f"unexpected parent directory: {src['parent']} != {parent_dir_name} -- {doc!r}"
        client_names_raw.append(src["name"])
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
        return [[], []]

    try:
        document = response.json()
    except ValueError:
        print("Response content is not valid JSON")
        print(url)
        print(response.content)
        return [[], []]

    if "disk_util" in document.keys():
        disknames = [
            disk["name"] for disk in document["disk_util"] if "name" in disk.keys()
        ]
    else:
        disknames = []

    if "client_stats" in document.keys():
        hostnames = list(
            set(
                [
                    host["hostname"]
                    for host in document["client_stats"]
                    if "hostname" in host.keys()
                ]
            )
        )
    else:
        hostnames = []

    return [disknames, hostnames]


def load_results(dirname, queue):
    """Load all the result data sample documents from files pushing them onto the
    given queue individually.
    """
    for filename in os.listdir(dirname):
        if not filename.endswith(".json"):
            continue
        if not filename.startswith("pbench_result_data_fio_"):
            continue

        print(f"Loading {filename}...", flush=True)
        with open(dirname + "/" + filename) as f:  # releases the handler itself
            data = json.load(f)

        print(f"Processing {filename}...", flush=True)
        for source in data["hits"]["hits"]:
            queue.put(source)
    queue.put(None)
    return


def load_results_gen(dirname, stats):
    """Load all the result data sample documents from files, yielding each one
    individually.
    """
    for filename in os.listdir(dirname):
        if not filename.endswith(".json"):
            continue
        if not filename.startswith("pbench_result_data_fio_"):
            continue

        print(f"Loading {filename}...", flush=True)
        with open(dirname + "/" + filename) as f:  # releases the handler itself
            data = json.load(f)

        print(f"Processing {filename}...", flush=True)
        for source in data["hits"]["hits"]:
            yield source
    return


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
        #    f"*** Result without a run: {run_ctrl}/{run_name}/{iter_name}"
        #    f"/{sample_name}/{sample_m_type}/{sample_m_title}"
        #    f"/{sample_m_idx}",
        #    flush=True,
        # )
        stats["missing_runs"] += 1
        return None

    if "mean" not in sample:
        # print(
        #    f"No 'mean' in {run_ctrl}/{run_name}/{iter_name}"
        #    f"/{sample_name}/{sample_m_type}/{sample_m_title}"
        #    f"/{sample_m_idx}",
        #    flush=True,
        # )
        stats["missing_mean"] += 1
        return None

    # The following field names are required
    try:
        benchmark = index["benchmark"]
        result = {
            "run.id": run_id,
            "run.name": run_name,
            "iteration.name": iter_name,
            "benchmark.bs": benchmark["bs"],
            "benchmark.direct": benchmark["direct"],
            "benchmark.ioengine": benchmark["ioengine"],
            "benchmark.max_stddevpct": benchmark["max_stddevpct"],
            "benchmark.primary_metric": benchmark["primary_metric"],
            "benchmark.rw": ", ".join(set((benchmark["rw"].split(",")))),
            "sample.name": sample_name,
            "sample.client_hostname": sample["client_hostname"],
            "sample.measurement_type": sample_m_type,
            "sample.measurement_title": sample_m_title,
            "sample.measurement_idx": sample_m_idx,
            "sample.mean": sample["mean"],
            "sample.stddev": sample["stddev"],
            "sample.stddevpct": sample["stddevpct"],
        }
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

    # optional workload parameters
    try:
        result["benchmark.filename"] = ", ".join(
            set((benchmark["filename"].split(",")))
        )
    except KeyError:
        result["benchmark.filename"] = "/tmp/fio"
    try:
        result["benchmark.iodepth"] = benchmark["iodepth"]
    except KeyError:
        result["benchmark.iodepth"] = "32"
    try:
        result["benchmark.size"] = ", ".join(set((benchmark["size"].split(","))))
    except KeyError:
        result["benchmark.size"] = "4096M"
    try:
        result["benchmark.numjobs"] = ", ".join(set((benchmark["numjobs"].split(","))))
    except KeyError:
        result["benchmark.numjobs"] = "1"
    try:
        result["benchmark.ramp_time"] = benchmark["ramp_time"]
    except KeyError:
        result["benchmark.ramp_time"] = "none"
    try:
        result["benchmark.runtime"] = benchmark["runtime"]
    except KeyError:
        result["benchmark.runtime"] = "none"
    try:
        result["benchmark.sync"] = benchmark["sync"]
    except KeyError:
        result["benchmark.sync"] = "none"
    try:
        result["benchmark.time_based"] = benchmark["time_based"]
    except KeyError:
        result["benchmark.time_based"] = "none"

    return result


def process_results(dirname, es_host, es_port, incoming_url, pool, pbench_runs, stats):
    """Intermediate generator for handling the fetching of the client names, disk
    names, and host names.

    """
    stats["total_recs"] = 0
    stats["missing_mean"] = 0
    stats["missing_runs"] = 0
    stats["errors"] = 0
    stats["mean"] = 0

    results_seen = dict()

    for source in load_results_gen(dirname, pbench_runs, stats):
        stats["total_recs"] += 1
        result = transform_result(source, pbench_runs, results_seen, stats)
        if result is None:
            continue
        yield result


def process_results_q(queue, es_host, es_port, incoming_url, pool, pbench_runs, stats):
    """Intermediate generator for handling the fetching of the client names, disk
    names, and host names.

    """
    stats["total_recs"] = 0
    stats["missing_mean"] = 0
    stats["missing_runs"] = 0
    stats["errors"] = 0
    stats["mean"] = 0

    results_seen = dict()

    source = queue.get()
    while source is not None:
        stats["total_recs"] += 1
        result = transform_result(source, pbench_runs, results_seen, stats)
        if result is not None:
            yield result
        source = queue.get()


def main(args):
    # Number of CPUs to use (where 0 = n CPUs)
    concurrency = int(args[1])

    es_host = args[2]
    es_port = args[3]

    # URL prefix to fetch unpacked data
    url_prefix = args[4]
    incoming_url = f"{url_prefix}/incoming/"

    # Directory containing the pbench run and result data pulled from
    # Elasticsearch.
    #
    # Collect both the pbench run data and result data for fio from 2020-06
    # (example month index name) from the Elasticsearch instance in the
    # directory argument using the following commands (they gives us the
    # performance results as well as the workload parameters, change the
    # dates and size fields accordingly):
    #
    # $ curl -XGET 'http://<es-host>:<es-port>/dsa-pbench.v4.result-data.2020-06-*/pbench-result-data-sample/_search?q=run.script:fio&size=63988&pretty=true' > pbench_result_data_fio_2020-06.json
    # $ curl -XGET 'http://<es-host>:<es-port>/dsa-pbench.v4.run.2020-06/pbench-run/_search?q=run.script:fio&size=13060&pretty=true' > pbench_run_data_fio_2020-06.json
    #
    # Provide the directory containing all those files as the 5th argument.
    dirname = args[5]

    # If requested, profile memory usage
    try:
        profile_arg = int(args[6])
    except (IndexError, ValueError):
        profile = False
    else:
        profile = profile_arg != 0

    if profile:
        from guppy import hpy

        memprof = hpy()
    else:
        memprof = None

    # We create the multiprocessing pool first to avoid forking a sub-process
    # with lots of memory allocated.
    ncpus = multiprocessing.cpu_count() - 1 if concurrency == 0 else concurrency
    pool = multiprocessing.Pool(ncpus) if ncpus != 1 else None

    scan_start = time.time()

    pbench_runs = load_pbench_runs(dirname, memprof)

    # Use a separate process for loading all the data from files.
    queue = multiprocessing.Queue(1000)
    reader = multiprocessing.Process(target=load_results, args=(dirname, queue,))
    reader.start()

    result_cnt = 0
    stats = dict()

    with open("sosreport_fio.txt", "w") as log, open(
        "output_latest_fio.json", "w"
    ) as outfile:
        for result in process_results_q(
            queue, es_host, es_port, incoming_url, pool, pbench_runs, stats
        ):
            result_cnt += 1
            for sos in result["sosreports"].keys():
                log.write("{}\n".format(sos))
            json.dump(result, outfile)

    scan_end = time.time()
    duration = scan_end - scan_start

    reader.join()

    print(f"final number of records: {result_cnt:n}", flush=True)
    print(json.dumps(stats, indent=4), flush=True)
    print(f"--- merging run and result data took {duration:0.2f} seconds", flush=True)

    return 0

    results, result_to_run, run_to_results = extract_pbench_results(dirname, memprof)
    pbench_fio = extract_pbench_runs(
        dirname,
        es_host,
        es_port,
        results,
        result_to_run,
        run_to_results,
        incoming_url,
        pool,
        memprof,
    )

    with open("sosreport_fio.txt", "w") as log:
        for id in pbench_fio:
            for sos in pbench_fio[id]["sosreports"].keys():
                log.write("{}\n".format(sos))

    print("final number of records: " + str(len(pbench_fio)))

    with open("output_latest_fio.json", "w") as outfile:
        json.dump(pbench_fio, outfile)

    scan_end = time.time()
    duration = scan_end - scan_start
    print(f"--- merging run and result data took {duration:0.2f} seconds")

    return 0


# point of entry
if __name__ == "__main__":
    status = main(sys.argv)
