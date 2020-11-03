#!/usr/bin/env python3
# -*- mode: python -*-

"""Pbench indexing driver, responsible for indexing a single pbench tar ball
into the configured Elasticsearch V1 instance.

"""

import sys
import os
import signal
from pathlib import Path
from argparse import ArgumentParser
from configparser import Error as ConfigParserError

from pbench.common.exceptions import (
    BadConfig,
    ConfigFileError,
    JsonFileError,
)
from pbench.server.indexer import IdxContext
from pbench.server.indexing_tarballs import Index, SigTermException


def sigterm_handler(*args):
    raise SigTermException()


# Internal debugging flag.
_DEBUG = 0


def main(options, name):
    """Main entry point to pbench-index.

       The caller is required to pass the "options" argument with the following
       expected attributes:
           cfg_name              - Name of the configuration file to use
           dump_index_patterns   - Don't do any indexing, but just emit the
                                   list of index patterns that would be used
           dump_templates        - Dump the templates that would be used
           index_tool_data       - Index tool data only
           re_index              - Consider tar balls marked for re-indexing
       All exceptions are caught and logged to syslog with the stacktrace of
       the exception in a sub-object of the logged JSON document.

       Status codes used by es_index and the error below are defined from the
       list below to maintain compatibility with the previous code base when
       pbench-index was a bash script and invoked index-pbench (yes, a bit
       confusing), the predecessor to this program.  The codes were used to
       sort the errors we encountered processing tar balls in to categories
       of retry or not:

            0 - normal, successful exit, no errors
            1 - Operational error while indexing
            2 - Configuration file not specified
            3 - Bad configuration file
            4 - Tar ball does not contain a metadata.log file
            5 - Bad start run date value encountered
            6 - File Not Found error
            7 - Bad metadata.log file encountered
            8 - Error reading a mapping file for Elasticsearch templates
            9 - Error creating one of the Elasticsearch templates
           10 - Bad hostname in a sosreport
           11 - Failure unpacking the tar ball
           12 - generic error, needs to be investigated and can be retried
                after any indexing bugs are fixed.

       Return Values (now a sub-set of the original status codes above):
         0 - Successfully processed all tar balls (errors processing tar
             balls are reported in the logs and in index status reports)
         1 - Failed to process one or more tar balls for unknown reasons
             (see logs)
         2 - Missing configuration file
         3 - Invalid configuration file
         8 - Unable to load and process expected mapping files
         9 - Unable to update index templates in configured Elasticsearch
             instance

        Signal Handlers used to establish different patterns for the three
        behaviors:

        1. Gracefully stop processing tar balls
            - SIGQUIT
            - The current tar ball is indexed until completion, but no other
              tar balls are processed.
            - Handler Behavior:
                - Sets a flag that causes the code flow to break out of the
                  for loop.
                - Does not raise an exception.

        2. Interrupt the current tar ball being indexed, and proceed to the
           next one, if any
            - SIGINT
            - Handler Behavior:
                - try/except/finally placed immediately around the es_index()
                  call so that the signal handler will only be established for
                  the duration of the call.
                - Raises an exception caught by above try/except/finally.
                - The finally clause would take down the signal handler.

        3. Stop processing tar balls immediately and exit gracefully
            - SIGTERM
            - Handler Behavior:
                - Raises an exception caught be a new, outer-most, try/except
                  block that does not have a finally clause (as you don't want
                  any code execution in the finally block).
    """

    _name_suf = "-tool-data" if options.index_tool_data else ""
    _name_re = "-re" if options.re_index else ""
    name = f"{name}{_name_re}{_name_suf}"

    if not options.cfg_name:
        print(
            f"{name}: ERROR: No config file specified; set"
            " _PBENCH_SERVER_CONFIG env variable or"
            " use --config <file> on the command line",
            file=sys.stderr,
        )
        return 2

    idxctx = None
    try:
        idxctx = IdxContext(options, name, _dbg=_DEBUG)
    except (ConfigFileError, ConfigParserError) as e:
        print(f"{name}: {e}", file=sys.stderr)
        return 2
    except BadConfig as e:
        print(f"{name}: {e}", file=sys.stderr)
        return 3
    except JsonFileError as e:
        print(f"{name}: {e}", file=sys.stderr)
        return 8

    if options.dump_index_patterns:
        idxctx.templates.dump_idx_patterns()
        return 0

    if options.dump_templates:
        idxctx.templates.dump_templates()
        return 0

    res = 0

    ARCHIVE_rp = idxctx.config.ARCHIVE

    INCOMING_rp = idxctx.config.INCOMING
    INCOMING_path = idxctx.config.get_valid_dir_option(
        "INCOMING", INCOMING_rp, idxctx.logger
    )
    if not INCOMING_path:
        res = 3

    qdir = idxctx.config.get_conf(
        "QUARANTINE", "pbench-server", "pbench-quarantine-dir", idxctx.logger
    )
    if not qdir:
        res = 3
    else:
        qdir_path = idxctx.config.get_valid_dir_option(
            "QDIR", Path(qdir), idxctx.logger
        )
        if not qdir_path:
            res = 3

    if res != 0:
        # Exit early if we encounter any errors.
        return res

    idxctx.logger.debug("{}.{}: starting", name, idxctx.TS)

    idx = Index(name, options, idxctx, INCOMING_rp)

    status, tarballs = idx.collect_tb(ARCHIVE_rp, qdir)
    if status == 0 and tarballs:
        status = idx.process_tb(tarballs)

    return status


if __name__ == "__main__":
    run_name = Path(sys.argv[0]).name
    run_name = run_name if run_name[-3:] != ".py" else run_name[:-3]
    if run_name not in ("pbench-index",):
        print(f"unexpected command file name: {run_name}", file=sys.stderr)
        sys.exit(1)
    parser = ArgumentParser(
        f"Usage: {run_name} [--config <path-to-config-file>] [--dump-index-patterns]"
        " [--dump_templates]"
    )
    parser.add_argument(
        "-C",
        "--config",
        dest="cfg_name",
        default=os.environ.get("_PBENCH_SERVER_CONFIG"),
        help="Specify config file",
    )
    parser.add_argument(
        "-I",
        "--dump-index-patterns",
        action="store_true",
        dest="dump_index_patterns",
        default=False,
        help="Emit a list of index patterns used",
    )
    parser.add_argument(
        "-Q",
        "--dump-templates",
        action="store_true",
        dest="dump_templates",
        default=False,
        help="Emit the full JSON document for each index template used",
    )
    parser.add_argument(
        "-T",
        "--tool-data",
        action="store_true",
        dest="index_tool_data",
        default=False,
        help="Only index tool data, assumes run data already exists",
    )
    parser.add_argument(
        "-R",
        "--re-index",
        action="store_true",
        dest="re_index",
        default=False,
        help="Perform re-indexing of previously indexed data",
    )
    parsed = parser.parse_args()
    try:
        # The SIGTERM handler is established around main() to make it easier
        # to handle it cleanly once established. We also make sure both
        # SIGQUIT and SIGINT are ignored until we are ready to deal with them.
        signal.signal(signal.SIGTERM, sigterm_handler)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGQUIT, signal.SIG_IGN)
        status = main(parsed, run_name)
    except SigTermException:
        # If a SIGTERM escapes the main indexing function, silently set our
        # exit status to 1.  All finally handlers would have been executed, no
        # need to report a SIGTERM again.
        status = 1
    sys.exit(status)
