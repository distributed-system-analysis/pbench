"""
Helper functions to get the elasticsearch specific configurations
"""

from dateutil import rrule

from configparser import NoSectionError, NoOptionError


def get_user_term(user: str):
    """Elasticsearch doesn't index (or search for) null values, and it's not
    clear we really want to consider "owner": null to be "owned" datasets, in
    any case. (Nor will they be possible beyond the transition period where we
    may retain limited support for 0.69 data.)

    Instead, let a query for data with a missing or null "user" parameter find
    all data that's set to allow public access. This by default includes all
    "unowned" data, but also data owned by a user that's been published.
    """
    if user:
        term = {"authorization.owner": user}
    else:
        term = {"authorization.access": "public"}
    return term


def get_es_host(config):
    try:
        return config.get("elasticsearch", "host")
    except (NoOptionError, NoSectionError):
        return ""


def get_es_port(config):
    try:
        return config.get("elasticsearch", "port")
    except (NoOptionError, NoSectionError):
        return ""


def get_es_url(config):
    try:
        return f"http://{get_es_host(config)}:{get_es_port(config)}"
    except (NoOptionError, NoSectionError):
        return ""


def get_index_prefix(config):
    try:
        return config.get("Indexing", "index_prefix")
    except (NoOptionError, NoSectionError):
        return ""


def gen_month_range(prefix, index, start, end):
    """
    gen_month_range Construct a comma-separated list of index names
    qualified by year and month suitable for use in the Elasticsearch
    /_search query URI.

    The month is incremented by 1 from "start" to "end"; for example,

    gen_month_range('drb.', 'v4.run.', '2020-08', '2020-10') will result
    in

        'drb.v4.run.2020-08,drb.v4.run.2020-09,drb.v4.run.2020-10,'

    This code is adapted from Javascript in the Pbench dashboard's
    'moment_constants.js' getAllMonthsWithinRange function.

    Args:
        prefix ([string]): The Pbench server index prefix
        index ([string]): The desired monthly index root
        start ([datetime.datetime]): The start time
        end ([datetime.datetime]): The end time

    Returns:
        [string]: A comma-separated list of month-qualified index names
    """
    monthResults = list()
    queryString = ""
    for m in rrule.rrule(rrule.MONTHLY, dtstart=start, until=end):
        monthResults.append(m.strftime("%Y-%m"))

    # TODO: hardcoding the index here is risky. We need a framework to
    # help the web services understand index versions and template
    # formats, probably by building a persistent database from the
    # index template documents at startup. This is TBD.
    for monthValue in monthResults:
        if index == "v4.result-data.":
            queryString += f"{prefix + index + monthValue}-*,"
        else:
            queryString += f"{prefix + index + monthValue},"
    return queryString
