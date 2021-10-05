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
    for file in os.listdir(dirname):
        if file.endswith(".py"):  # code
            continue
        else:
            with open(dirname + "/" + file) as f:  # releases the handler itself
                data = json.load(f)
                for source in data["hits"]["hits"]:

                    # counts
                    total_recs = total_recs + 1
                    if "mean" in source["_source"]["sample"]:
                        mean = mean + 1
                        assert source["_id"] not in results.keys(), "Result id repeated"
                        index = source["_source"]
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
                            "benchmark.ramp_time": index["benchmark"]["ramp_time"],
                            "benchmark.runtime": index["benchmark"]["runtime"],
                            "benchmark.rw": ", ".join(
                                set((index["benchmark"]["rw"].split(",")))
                            ),
                            "benchmark.sync": index["benchmark"]["sync"],
                            "benchmark.time_based": index["benchmark"]["time_based"],
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

                        result_to_run[source["_id"]] = index["run"]["id"]

    print("total pbench result records: " + str(total_recs))
    print("records with mean available: " + str(mean))

    return results, result_to_run


# extract controller directory and sosreports'
# names associated with each pbench run and
# merge it with the result data
def extract_pbench_runs(filename, results, result_to_run, incoming_url, pool):
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

    with open(filename) as f:  # releases the handler itself
        data = json.load(f)
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

            if source["_source"]["@metadata"]["md5"] not in result_to_run.values():
                run_wo_res = run_wo_res + 1
                print(f"run without results: {source['_source']['run']['name']}")
            else:
                valid_run = True

            if "sosreports" in source["_source"]:
                sos = sos + 1
            # counts

            if valid_run and "sosreports" in source["_source"]:
                result_list.append(
                    pool.apply_async(
                        extract_run_metadata,
                        args=(results, result_to_run, source["_source"], incoming_url,),
                    )
                )
                # result_list.append(extract_run_metadata(results, result_to_run, source['_source'], incoming_url))

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

    temp = dict()
    clientnames_set = False  # since clientnames are common to all iterations
    current_sample_name = (
        None  # since disknames and hostnames are common to all samples
    )

    # print ("Entered run metadata")
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
                disknames, hostnames = extract_fio_result(results[id], incoming_url)
                current_sample_name = results[id]["sample.name"]
            results[id]["disknames"] = disknames
            results[id]["hostnames"] = hostnames

            # add client names here
            if not clientnames_set:
                # print ("Before clients")
                clientnames = extract_clients(results[id], incoming_url)
                clientnames_set = True
            results[id]["clientnames"] = clientnames

            temp[id] = results[id]

    return temp


# extract list of clients from the URL
def extract_clients(results_meta, incoming_url):
    names = dict()
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
    r = requests.head(url, allow_redirects=True)
    if r.status_code == 200:  # successful
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        tbl = soup.find("table")
        df = pd.read_html(str(tbl))[0]
        df = df[(~df["Name"].isnull()) & (df["Name"] != "Parent Directory")]
        clientnames = df["Name"].to_list()

    if "clientnames" not in locals():
        clientnames = []

    return clientnames


# extract host and disk names from fio-result.txt
def extract_fio_result(results_meta, incoming_url):
    names = dict()
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
    r = requests.head(url, allow_redirects=True)
    if r.status_code == 200:  # successful
        page = requests.get(url)
        try:
            response = page.json()
        except ValueError:
            print("Response content is not valid JSON")
            print(url)
            print(page.content)
            return [[], []]

        if "disk_util" in response.keys():
            disknames = [
                disk["name"] for disk in response["disk_util"] if "name" in disk.keys()
            ]
        if "client_stats" in response.keys():
            hostnames = [
                host["hostname"]
                for host in response["client_stats"]
                if "hostname" in host.keys()
            ]
            hostnames = list(set(hostnames))

    if "disknames" not in locals():
        disknames = []
    if "hostnames" not in locals():
        hostnames = []

    return [disknames, hostnames]


def main(args):
    concurrency = int(args[1])  # Number of CPUs to use (where 0 = n CPUs)
    url_prefix = args[2]  # URL prefix to fetch unpacked data
    dirname = args[3]  # indexed pbench results data
    filename = args[4]  # indexed pbench runs data

    incoming_url = f"{url_prefix}/incoming/"

    # We create the multiprocessing pool first to avoid forking a sub-process
    # with lots of memory allocated.
    ncpus = multiprocessing.cpu_count() - 1 if concurrency == 0 else concurrency
    pool = multiprocessing.Pool(ncpus)

    scan_start = time.time()

    results, result_to_run = extract_pbench_results(dirname)
    pbench_fio = extract_pbench_runs(
        filename, results, result_to_run, incoming_url, pool
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
