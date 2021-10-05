#!/usr/bin/env python3

import os
import sys
import time
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup
import multiprocessing


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
            iter_name = (index["iteration"]["name"],)
            sample = index["sample"]
            sample_name = (sample["name"],)
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
    dirname, results, result_to_run, run_to_results, incoming_url, pool, memprof
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
                                incoming_url,
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
                            incoming_url,
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
    results, result_to_run, run_to_results, run_record, incoming_url
):
    # print (f"Entered run metadata: {run_record['run']['name']}")

    temp = dict()

    # since clientnames are common to all iterations
    clientnames_set = False

    # since disknames and hostnames are common to all samples
    current_sample_name = None

    session = requests.Session()
    ua = session.headers["User-Agent"]
    session.headers.update({"User-Agent": f"{ua} -- merge_sos_and_perf_parallel"})

    # FIXME - we are going to update each result that has the run record's MD5
    # for its ID.
    #
    # 2. We should only process the "run_record" sosreports once first, and
    # then add that result to each result record
    #
    # 3. Both the fio and the client calculations should be done once for each
    # sample, so no need to track clientnames_set
    #
    # 4. The current sample name CAN BE the same name between iterations, so
    # we need to gather them all, calculate the list of individual iteration/sample
    # names, and then fetch the values for those, and assign to records
    for result_id in run_to_results[run_record["@metadata"]["md5"]]:
        result = results[result_id]
        result["controller_dir"] = run_record["@metadata"]["controller_dir"]
        result["sosreports"] = dict()
        for sosreport in run_record["sosreports"]:
            result["sosreports"][os.path.split(sosreport["name"])[1]] = {
                "hostname-s": sosreport["hostname-s"],
                "hostname-f": sosreport["hostname-f"],
                "time": sosreport["name"].split("/")[2],
            }

        # add host and disk names in the data here
        if current_sample_name != result["sample.name"]:
            # print ("Before fio")
            disknames, hostnames = extract_fio_result(result, incoming_url, session)
            current_sample_name = result["sample.name"]
        result["disknames"] = disknames
        result["hostnames"] = hostnames

        # add client names here
        if not clientnames_set:
            # print ("Before clients")
            clientnames = extract_clients(result, incoming_url, session)
            clientnames_set = True
        result["clientnames"] = clientnames

        temp[result_id] = result

    return temp


# extract list of clients from the URL
def extract_clients(results_meta, incoming_url, session):
    url = (
        incoming_url
        + results_meta["controller_dir"]
        + "/"
        + results_meta["run.name"]
        + "/"
        + results_meta["iteration.name"]
        + "/"
        + results_meta["sample.name"]
        + "/clients/"
    )

    # check if the page is accessible
    response = session.get(url, allow_redirects=True)
    if response.status_code != 200:  # successful
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    tbl = soup.find("table")
    df = pd.read_html(str(tbl))[0]
    df = df[(~df["Name"].isnull()) & (df["Name"] != "Parent Directory")]
    clientnames = df["Name"].to_list()

    return clientnames


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


def main(args):
    # Number of CPUs to use (where 0 = n CPUs)
    concurrency = int(args[1])

    # URL prefix to fetch unpacked data
    url_prefix = args[2]
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
    # Provide the directory containing all those files as the 3rd argument.
    dirname = args[3]

    # If requested, profile memory usage
    try:
        profile_arg = int(args[4])
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

    results, result_to_run, run_to_results = extract_pbench_results(dirname, memprof)
    pbench_fio = extract_pbench_runs(
        dirname, results, result_to_run, run_to_results, incoming_url, pool, memprof
    )

    with open("sosreport_fio.txt", "w") as log:
        for id in pbench_fio:
            for sos in pbench_fio[id]["sosreports"].keys():
                log.write("{}\n".format(sos))

    print("final number of records: " + str(len(pbench_fio)))

    with open("output_latest_fio.json", "w") as outfile:
        json.dump(pbench_fio, outfile)

    # print(json.dumps(pbench_fio, indent = 4))

    scan_end = time.time()
    duration = scan_end - scan_start
    print(f"--- merging run and result data took {duration:0.2f} seconds")

    return 0


# point of entry
if __name__ == "__main__":
    status = main(sys.argv)
