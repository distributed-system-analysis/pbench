#!/usr/bin/env python3

import argparse
from datetime import datetime
import time

from dateutil import rrule
from dateutil.relativedelta import relativedelta
from elasticsearch1 import Elasticsearch
from pbench_combined_data import PbenchCombinedDataCollection
import requests


def _year_month_gen(
    end_time: datetime, start_months_prior: int, end_months_prior: int
) -> str:
    """Generate YYYY-MM stings for months specified.

    For all months inclusive, generate YYYY-MM strings starting at the
    month of the end_time, and ending start_months_prior before the end_time.

    Parameters
    ----------
    end_time : datetime
        The time for the last month desired
    start_months_prior : int
        Number of months before the end_time to end
        string generation.

    Yields
    ------
    month_str : str
        month string in the YYYY-MM format

    """
    start = end_time - relativedelta(months=start_months_prior)
    first_month = start.replace(day=1)
    last_month = (
        end_time + relativedelta(day=31) - relativedelta(months=end_months_prior)
    )
    reverse_months = sorted(
        rrule.rrule(rrule.MONTHLY, dtstart=first_month, until=last_month), reverse=True
    )
    for date in reverse_months:
        yield f"{date.year:04}-{date.month:02}"


def main(parser: argparse.ArgumentParser) -> None:
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

    if args.profile_memory_usage:
        from guppy import hpy

        memprof = hpy()
    else:
        memprof = None

    if memprof:
        print(f"Initial memory profile ... {memprof.heap()}", flush=True)

    es = Elasticsearch(
        [f"{args.es_host}:{args.es_port}"], timeout=200
    )  # to prevent read timeout errors (60 is arbitrary)

    session = requests.Session()
    ua = session.headers["User-Agent"]
    session.headers.update({"User-Agent": f"{ua} -- {parser.prog}"})
    pbench_data = PbenchCombinedDataCollection(
        args.url_prefix,
        args.sos_host_server,
        session,
        es,
        args.record_limit,
        args.cpu_n,
    )

    scan_start = time.time()
    end_time = datetime.utcfromtimestamp(scan_start)

    # pbench_data.sync_add_months(
    #     _year_month_gen(end_time, args.start_months_prior, args.end_months_prior)
    # )

    pbench_data.aggregate_data(
        _year_month_gen(end_time, args.start_months_prior, args.end_months_prior)
    )

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
    parser.add_argument(
        "sos_host_server",
        action="store",
        type=str,
        help="Sosreport host server to access sosreport info",
    )
    parser.add_argument(
        "--cpu",
        action="store",
        dest="cpu_n",
        type=int,
        default=0,
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
        "--months_s",
        action="store",
        dest="start_months_prior",
        type=int,
        default=12,  # default to 12 months worth of data
        help="Number of months prior to now at which to start data collection",
    )
    parser.add_argument(
        "--months_e",
        action="store",
        dest="end_months_prior",
        type=int,
        default=0,  # setting so have usable data for testing
        help="Number of months prior to now at which to end data collection",
    )
    return parser


# point of entry
if __name__ == "__main__":
    args = parse_arguments()
    main(args)
