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
def extract_pbench_results(dirname):

    # counts
    total_recs = 0
    mean = 0
    # counts

    results = dict()
    result_to_run = dict()  # maps result id to run id
    for filename in os.listdir(dirname):
        if not filename.endswith(".json"):  # code
            continue
        if not filename.startswith("pbench_result_data_fio_"):
            continue
        print(f"Processing {filename}...", flush=True)
        with open(dirname + "/" + filename) as f:  # releases the handler itself
            data = json.load(f)
            for source in data["hits"]["hits"]:

                # counts
                total_recs = total_recs + 1
                if "mean" in source["_source"]["sample"]:
                    mean = mean + 1
                    assert source["_id"] not in results.keys(), "Result id repeated"
                    index = source["_source"]
                    try:
                        results[source["_id"]] = {
                            "run.id": index["run"]["id"],
                            # 'run.controller' : index['run']['controller'],
                            "run.name": index["run"]["name"],
                            "iteration.name": index["iteration"]["name"],
                            "benchmark.bs": index["benchmark"]["bs"],
                            "benchmark.direct": index["benchmark"]["direct"],
                            "benchmark.ioengine": index["benchmark"]["ioengine"],
                            "benchmark.max_stddevpct": index["benchmark"][
                                "max_stddevpct"
                            ],
                            "benchmark.primary_metric": index["benchmark"][
                                "primary_metric"
                            ],
                            "benchmark.rw": ", ".join(
                                set((index["benchmark"]["rw"].split(",")))
                            ),
                            "sample.name": index["sample"]["name"],
                            "sample.client_hostname": index["sample"][
                                "client_hostname"
                            ],
                            "sample.measurement_type": index["sample"][
                                "measurement_type"
                            ],
                            "sample.measurement_title": index["sample"][
                                "measurement_title"
                            ],
                            "sample.mean": index["sample"]["mean"],
                            "sample.stddev": index["sample"]["stddev"],
                            "sample.stddevpct": index["sample"]["stddevpct"],
                        }
                    except KeyError as exc:
                        print(
                            f"ERROR - {filename}, {exc}, {json.dumps(index)}",
                            file=sys.stderr,
                        )
                        continue

                    # optional workload parameters
                    if "filename" not in index["benchmark"]:
                        results[source["_id"]]["benchmark.filename"] = "/tmp/fio"
                    else:
                        results[source["_id"]]["benchmark.filename"] = ", ".join(
                            set((index["benchmark"]["filename"].split(",")))
                        )
                    if "iodepth" not in index["benchmark"]:
                        results[source["_id"]]["benchmark.iodepth"] = "32"
                    else:
                        results[source["_id"]]["benchmark.iodepth"] = index[
                            "benchmark"
                        ]["iodepth"]
                    if "size" not in index["benchmark"]:
                        results[source["_id"]]["benchmark.size"] = "4096M"
                    else:
                        results[source["_id"]]["benchmark.size"] = ", ".join(
                            set((index["benchmark"]["size"].split(",")))
                        )
                    if "numjobs" not in index["benchmark"]:
                        results[source["_id"]]["benchmark.numjobs"] = "1"
                    else:
                        results[source["_id"]]["benchmark.numjobs"] = ", ".join(
                            set((index["benchmark"]["numjobs"].split(",")))
                        )
                    try:
                        results[source["_id"]]["benchmark.ramp_time"] = index[
                            "benchmark"
                        ]["ramp_time"]
                    except KeyError:
                        results[source["_id"]]["benchmark.ramp_time"] = "none"
                    try:
                        results[source["_id"]]["benchmark.runtime"] = index[
                            "benchmark"
                        ]["runtime"]
                    except KeyError:
                        results[source["_id"]]["benchmark.runtime"] = "none"
                    try:
                        results[source["_id"]]["benchmark.sync"] = index["benchmark"][
                            "sync"
                        ]
                    except KeyError:
                        results[source["_id"]]["benchmark.sync"] = "none"
                    try:
                        results[source["_id"]]["benchmark.time_based"] = index[
                            "benchmark"
                        ]["time_based"]
                    except KeyError:
                        results[source["_id"]]["benchmark.time_based"] = "none"

                    result_to_run[source["_id"]] = index["run"]["id"]

    print("total pbench result records: " + str(total_recs))
    print("records with mean available: " + str(mean))

    return results, result_to_run


# extract controller directory and sosreports'
# names associated with each pbench run and
# merge it with the result data
def extract_pbench_runs(dirname, results, result_to_run, incoming_url, pool):
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

    # Significantly speeds up valid run check below
    expected_run_ids = set(result_to_run.values())

    for filename in os.listdir(dirname):
        if not filename.endswith(".json"):  # code
            continue
        if not filename.startswith("pbench_run_data_fio_"):
            continue
        print(f"Processing {filename}...", flush=True)
        with open(dirname + "/" + filename) as f:  # releases the handler itself
            data = json.load(f)
            for source in data["hits"]["hits"]:

                # counts
                total_recs = total_recs + 1
                if "controller_dir" in source["_source"]["@metadata"]:
                    controller_dir = controller_dir + 1
                    if source["_source"]["@metadata"]["controller_dir"].startswith(
                        "EC2::"
                    ):
                        cloud = cloud + 1
                else:
                    print(
                        "pbench run with no controller_dir: "
                        + source["_source"]["@metadata"]["md5"]
                    )
                    continue

                if source["_source"]["@metadata"]["md5"] not in expected_run_ids:
                    run_wo_res = run_wo_res + 1
                    print(
                        f"*** run without results: {source['_source']['run']['name']}"
                    )
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
                                    source["_source"],
                                    incoming_url,
                                ),
                            )
                        )
                    else:
                        pbench.update(
                            extract_run_metadata(
                                results, result_to_run, source["_source"], incoming_url
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
def extract_run_metadata(results, result_to_run, run_record, incoming_url):
    # print (f"Entered run metadata: {run_record['run']['name']}")

    temp = dict()
    clientnames_set = False  # since clientnames are common to all iterations
    current_sample_name = (
        None  # since disknames and hostnames are common to all samples
    )
    session = requests.Session()
    ua = session.headers["User-Agent"]
    session.headers.update({"User-Agent": f"{ua} -- merge_sos_and_perf_parallel"})

    # FIXME - we are going to update each result that has the run record's MD5
    # for its ID.
    #
    # 1. We should build table of run IDs mapped to a list of result IDs to
    # speed this up
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
    for id in result_to_run:
        if result_to_run[id] == run_record["@metadata"]["md5"]:
            results[id]["controller_dir"] = run_record["@metadata"]["controller_dir"]
            results[id]["sosreports"] = dict()
            for sosreport in run_record["sosreports"]:
                results[id]["sosreports"][os.path.split(sosreport["name"])[1]] = {
                    "hostname-s": sosreport["hostname-s"],
                    "hostname-f": sosreport["hostname-f"],
                    "time": sosreport["name"].split("/")[2],
                }

            # add host and disk names in the data here
            if current_sample_name != results[id]["sample.name"]:
                # print ("Before fio")
                disknames, hostnames = extract_fio_result(
                    results[id], incoming_url, session
                )
                current_sample_name = results[id]["sample.name"]
            results[id]["disknames"] = disknames
            results[id]["hostnames"] = hostnames

            # add client names here
            if not clientnames_set:
                # print ("Before clients")
                clientnames = extract_clients(results[id], incoming_url, session)
                clientnames_set = True
            results[id]["clientnames"] = clientnames

            temp[id] = results[id]

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

    # We create the multiprocessing pool first to avoid forking a sub-process
    # with lots of memory allocated.
    ncpus = multiprocessing.cpu_count() - 1 if concurrency == 0 else concurrency
    pool = multiprocessing.Pool(ncpus) if ncpus != 1 else None

    scan_start = time.time()

    results, result_to_run = extract_pbench_results(dirname)
    pbench_fio = extract_pbench_runs(
        dirname, results, result_to_run, incoming_url, pool
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
