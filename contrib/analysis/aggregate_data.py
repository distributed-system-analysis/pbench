#!/usr/bin/env python3

import argparse
import requests
import time

from datetime import datetime
from dateutil import rrule
from dateutil.relativedelta import relativedelta
from pbench_combined_data import PbenchCombinedDataCollection
from elasticsearch1 import Elasticsearch

def _month_gen(end_time: datetime, start_months_prior : int) -> str:
    """Generate YYYY-MM stings for months specified.
    
    For all months inclusive, generate YYYY-MM strings ending at the
    month of the end_time, and starting from start_months_prior months before
    the end_time.

    Parameters
    ----------
    end_time : datetime
        The time for the last month desired
    start_months_prior : int
        Number of months before the end_time to start
        string generation.
    
    Yields
    ------
    month_str : str
        month string in the YYYY-MM format

    """
    start = end_time - relativedelta(months=start_months_prior)
    first_month = start.replace(day=1)
    last_month = end_time + relativedelta(day=31)
    for m in rrule.rrule(rrule.MONTHLY, dtstart=first_month, until=last_month):
        yield f"{m.year:04}-{m.month:02}"


def main(parser : argparse.ArgumentParser) -> None:
    """Given cli args, sets up Elasticsearch and aggregates all data.

    Creates Elasticsearch instance and PbenchCombinedDataCollection
    object, which it then adds all the data to for the months generated
    from _month_gen given the args passed in. 

    Parameters
    ----------
    parser : argparse.ArgumentParser
        arguments passed in stored with easily accessible
        variable names, can be accessed by calling parse_args on it.
    
    Returns
    -------
    None
    
    """
    args = parser.parse_args()
    incoming_url = f"{args.url_prefix}/incoming/"

    if args.profile_memory_usage:
        from guppy import hpy

        memprof = hpy()
    else:
        memprof = None

    if memprof:
        print(f"Initial memory profile ... {memprof.heap()}", flush=True)

    es = Elasticsearch(
        [f"{args.es_host}:{args.es_port}"], timeout=60
    )  # to prevent read timeout errors (60 is arbitrary)

    session = requests.Session()
    ua = session.headers["User-Agent"]
    session.headers.update({"User-Agent": f"{ua} -- {parser.prog}"})
    pbench_data = PbenchCombinedDataCollection(
        incoming_url, session, es, args.record_limit
    )

    scan_start = time.time()
    end_time = datetime.utcfromtimestamp(scan_start)

    for month in _month_gen(end_time, args.start_months_prior):
        pbench_data.collect_data(month)
        # need to duplicate this code here so that limiting still works
        if pbench_data.record_limit != -1:
                if pbench_data.trackers["run"]["valid"] >= pbench_data.record_limit:
                    break

    scan_end = time.time()
    duration = scan_end - scan_start

    pbench_data.print_report()
    pbench_data.emit_csv()
    print(f"--- merging run and result data took {duration:0.2f} seconds", flush=True)

    if memprof:
        print(
            f"Final memory profile ... {memprof.heap()}",
            flush=True,
        )



def parse_arguments() -> argparse.ArgumentParser:
    """Specifies Command Line argument parsing.

    Gives help info when running this file as to what arguments needed, etc.
    Adds optional flags to change execution of code.

    Returns
    -------
    parser : argparse.ArgumentParser
        arguments passed in stored with easily accessible
        variable names, can be accessed by calling parse_args on it.

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
    parser.add_argument(
        "--months",
        action="store",
        dest="start_months_prior",
        type=int,
        default=12, # default to 12 months worth of data
        help="Number of months prior to now for which to collect data",
    )
    return parser


# point of entry
if __name__ == "__main__":
    args = parse_arguments()
    status = main(args)
