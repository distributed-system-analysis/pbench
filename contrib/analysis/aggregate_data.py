#!/usr/bin/env python3

import argparse

# import multiprocessing
import requests
import time

from datetime import datetime
from dateutil import rrule
from dateutil.relativedelta import relativedelta
from pbench_combined_data import PbenchCombinedDataCollection

from elasticsearch1 import Elasticsearch


def _month_gen(now: datetime) -> str:
    """Generate YYYY-MM stings from all the months, inclusively, between the
    given start and end dates.
    """
    start = now - relativedelta(years=1)
    first_month = start.replace(day=1)
    last_month = now + relativedelta(day=31)
    for m in rrule.rrule(rrule.MONTHLY, dtstart=first_month, until=last_month):
        yield f"{m.year:04}-{m.month:02}"


def main(args):

    incoming_url = f"{args.url_prefix}/incoming/"

    if args.profile_memory_usage:
        from guppy import hpy

        memprof = hpy()
    else:
        memprof = None

    if memprof:
        print(f"Initial memory profile ... {memprof.heap()}", flush=True)

    # We create the multiprocessing pool first to avoid forking a sub-process
    # with lots of memory allocated.
    # ncpus = multiprocessing.cpu_count() - 1 if args.cpu_n == 0 else args.cpu_n
    # pool = multiprocessing.Pool(ncpus) if ncpus != 1 else None

    es = Elasticsearch(
        [f"{args.es_host}:{args.es_port}"], timeout=60
    )  # to prevent read timeout errors (60 is arbitrary)

    session = requests.Session()
    ua = session.headers["User-Agent"]
    session.headers.update({"User-Agent": f"{ua} -- merge_sos_and_perf_parallel"})
    pbench_data = PbenchCombinedDataCollection(
        incoming_url, session, es, args.record_limit
    )

    scan_start = time.time()
    now = datetime.utcfromtimestamp(scan_start)

    # TODO: This doesn't work because es instance not pickle-able.
    # pool.starmap(merge_run_result_index, [(es, month, args.record_limit, pbench_data) for month in _month_gen(now)])

    for month in _month_gen(now):
        pbench_data.collect_data(month)

    # NOTE: Not writing sosreports and results to files. Will work on this step
    #       of sosreport processing, etc next.

    scan_end = time.time()
    duration = scan_end - scan_start

    print(pbench_data)
    print(f"--- merging run and result data took {duration:0.2f} seconds", flush=True)

    if memprof:
        print(
            f"Final memory profile ... {memprof.heap()}",
            flush=True,
        )

    return 0


def parse_arguments() -> argparse.Namespace:
    """Specifies Command Line argument parsing.

    Gives help info when running this file as to what arguments needed, etc.
    Adds optional flags to change execution of code.

    Returns
    -------
    args : argparse.Namespace
        arguments passed in stored with easily accessible
        variable names

    """
    parser = argparse.ArgumentParser(description="Host and Server Information")
    parser.add_argument(
        "es_host", action="store", type=str, help="Elasticsearch host name"
    )
    parser.add_argument(
        "es_port", action="store", type=int, help="Elasticsearch port number"
    )
    parser.add_argument(
        "url_prefix",
        action="store",
        type=str,
        help="Pbench server url prefix to extract host and disk names",
    )
    # parser.add_argument("sosreport_host_server", action="store" ,dest="sos_host", type=str, help="Sosreport host server to access sosreport info")
    parser.add_argument(
        "--cpu",
        action="store",
        dest="cpu_n",
        type=int,
        default=1,
        help="Number of CPUs to be used",
    )
    parser.add_argument(
        "--limit",
        action="store",
        dest="record_limit",
        type=int,
        default=-1,
        help="Number of desired acceptable results for processing",
    )  # Temporarily used -1 as default and it meaning all
    parser.add_argument(
        "--profile",
        action="store_true",
        dest="profile_memory_usage",
        help="Want memory usage profile",
    )
    args = parser.parse_args()
    return args


# point of entry
if __name__ == "__main__":
    args = parse_arguments()
    status = main(args)
