#!/usr/bin/env python3
# -*- mode: python -*-

"""Pbench indexing driver, responsible for indexing a single pbench tar ball
into the configured Elasticsearch V1 instance.

"""

import sys
import os
import glob
import tarfile
import tempfile
from argparse import ArgumentParser
from configparser import Error as ConfigParserError

from pbench import tstos, BadConfig, quarantine, rename_tb_link
from pbench.indexer import (
    IdxContext,
    ConfigFileError,
    BadDate,
    UnsupportedTarballFormat,
    BadMDLogFormat,
    SosreportHostname,
    PbenchTarBall,
    es_index,
    JsonFileError,
    TemplateError,
    VERSION,
)
from pbench.report import Report


# Internal debugging flag.
_DEBUG = 0

# ^$!@!#%# compatibility
# FileNotFoundError is python 3.3 and the travis-ci hosts still (2015-10-01) run
# python 3.2
_filenotfounderror = getattr(__builtins__, "FileNotFoundError", IOError)


def _count_lines(fname):
    """Simple method to count the lines of a file.
    """
    try:
        with open(fname, "r") as fp:
            cnt = sum(1 for line in fp)
    except _filenotfounderror:
        cnt = 0
    return cnt


def main(options, name):
    """Main entry point to pbench-index.

       The caller is required to pass the "options" argument with the following
       expected attributes:
           cfg_name              - Name of the configuration file to use
           dump_index_patterns   - Don't do any indexing, but just emit the
                                   list of index patterns that would be used
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
    """
    if not options.cfg_name:
        print(
            "{}: ERROR: No config file specified; set _PBENCH_SERVER_CONFIG env variable or"
            " use --config <file> on the command line".format(name),
            file=sys.stderr,
        )
        return 2

    if options.index_tool_data:
        name = "{}-tool-data".format(name)

    idxctx = None
    try:
        idxctx = IdxContext(options, name, _dbg=_DEBUG)
    except (ConfigFileError, ConfigParserError) as e:
        print("{}: {}".format(name, e), file=sys.stderr)
        return 2
    except BadConfig as e:
        print("{}: {}".format(name, e), file=sys.stderr)
        return 3
    except JsonFileError as e:
        print("{}: {}".format(name, e), file=sys.stderr)
        return 8

    if options.dump_index_patterns:
        idxctx.templates.dump_idx_patterns()
        return 0

    if options.dump_templates:
        idxctx.templates.dump_templates()
        return 0

    if options.index_tool_data:
        # The link source and destination for the operation of this script
        # when it only indexes tool data.
        linksrc = "TO-INDEX-TOOL"
        linkdest = "INDEXED"
    else:
        # The link source and destination for the operation of this script
        # when it indexes run, table-of-contents, and result data.
        linksrc = "TO-INDEX"
        linkdest = "TO-INDEX-TOOL"
    # We only ever use a symlink'd error destination for indexing
    # problems.
    linkerrdest = "WONT-INDEX"

    res = 0
    try:
        ARCHIVE_rp = os.path.realpath(idxctx.config.ARCHIVE)
        if not os.path.isdir(ARCHIVE_rp):
            idxctx.logger.error("{}: Bad ARCHIVE={}", name, idxctx.config.ARCHIVE)
            res = 3
        INCOMING_rp = os.path.realpath(idxctx.config.INCOMING)
        if not os.path.isdir(INCOMING_rp):
            idxctx.logger.error("{}: Bad INCOMING={}", name, idxctx.config.INCOMING)
            res = 3
        qdir = idxctx.config.get("pbench-server", "pbench-quarantine-dir")
        if not os.path.isdir(qdir):
            idxctx.logger.error(
                "{}: {} does not exist, or is not a directory", name, qdir
            )
            res = 3
    except Exception:
        idxctx.logger.exception("{}: Unexpected setup error", name)
        res = 12

    if res != 0:
        # Exit early if we encounter any errors.
        return res

    idxctx.logger.debug("{}.{}: starting", name, idxctx.TS)

    # find -L $ARCHIVE/*/$linksrc -name '*.tar.xz' -printf "%s\t%p\n" 2>/dev/null | sort -n > $list
    tarballs = []
    try:
        tb_glob = os.path.join(ARCHIVE_rp, "*", linksrc, "*.tar.xz")
        for tb in glob.iglob(tb_glob):
            try:
                rp = os.path.realpath(tb)
            except OSError:
                idxctx.logger.warning("{} does not resolve to a real path", tb)
                quarantine(qdir, idxctx.logger, tb)
                continue
            controller_path = os.path.dirname(rp)
            controller = os.path.basename(controller_path)
            archive_path = os.path.dirname(controller_path)
            if archive_path != ARCHIVE_rp:
                idxctx.logger.warning(
                    "For tar ball {}, original home is not {}", tb, ARCHIVE_rp
                )
                quarantine(qdir, idxctx.logger, tb)
                continue
            if not os.path.isfile(rp + ".md5"):
                idxctx.logger.warning("Missing .md5 file for {}", tb)
                quarantine(qdir, idxctx.logger, tb)
                # Audit should pick up missing .md5 file in ARCHIVE directory.
                continue
            try:
                # get size
                size = os.path.getsize(rp)
            except OSError:
                idxctx.logger.warning("Could not fetch tar ball size for {}", tb)
                quarantine(qdir, idxctx.logger, tb)
                # Audit should pick up missing .md5 file in ARCHIVE directory.
                continue
            else:
                tarballs.append((size, controller, tb))
    except Exception:
        idxctx.logger.exception(
            "Unexpected error encountered generating list" " of tar balls to process"
        )
        return 12
    else:
        if not tarballs:
            idxctx.logger.info("No tar balls found that need processing")
            return 0

    # We always process the smallest tar balls first.
    tarballs = sorted(tarballs)

    # At this point, tarballs contains a list of tar balls sorted by size
    # that were available as symlinks in the various 'linksrc' directories.
    idxctx.logger.debug("Preparing to index {:d} tar balls", len(tarballs))

    try:
        # Now that we are ready to begin the actual indexing step, ensure we
        # have the proper index templates in place.
        idxctx.logger.debug("update_templates [start]")
        idxctx.templates.update_templates(idxctx.es)
    except TemplateError as e:
        idxctx.logger.error("update_templates [end], error {}", repr(e))
        res = 9
    except Exception:
        idxctx.logger.exception(
            "update_templates [end]: Unexpected template" " processing error"
        )
        res = 12
    else:
        idxctx.logger.debug("update_templates [end]")
        res = 0

    if res != 0:
        # Exit early if we encounter any errors.
        return res

    report = Report(
        idxctx.config,
        name,
        es=idxctx.es,
        pid=idxctx.getpid(),
        group_id=idxctx.getgid(),
        user_id=idxctx.getuid(),
        hostname=idxctx.gethostname(),
        version=VERSION,
        templates=idxctx.templates,
    )
    # We use the "start" report ID as the tracking ID for all indexed
    # documents.
    try:
        tracking_id = report.post_status(tstos(idxctx.time()), "start")
    except Exception:
        idxctx.logger.error("Failed to post initial report status")
        return 12
    else:
        idxctx.set_tracking_id(tracking_id)

    with tempfile.TemporaryDirectory(
        prefix="{}.".format(name), dir=idxctx.config.TMP
    ) as tmpdir:
        idxctx.logger.debug("start processing list of tar balls")
        tb_list = os.path.join(tmpdir, "{}.{}.list".format(name, idxctx.TS))
        try:
            with open(tb_list, "w") as lfp:
                # Write out all the tar balls we are processing so external
                # viewers can follow along from home.
                for size, controller, tb in tarballs:
                    print("{:20d} {} {}".format(size, controller, tb), file=lfp)

            indexed = os.path.join(tmpdir, "{}.{}.indexed".format(name, idxctx.TS))
            erred = os.path.join(tmpdir, "{}.{}.erred".format(name, idxctx.TS))
            skipped = os.path.join(tmpdir, "{}.{}.skipped".format(name, idxctx.TS))
            ie_filename = os.path.join(
                tmpdir, "{}.{}.indexing-errors.json".format(name, idxctx.TS)
            )

            for size, controller, tb in tarballs:
                # Sanity check source tar ball path
                linksrc_dir = os.path.dirname(tb)
                linksrc_dirname = os.path.basename(linksrc_dir)
                assert linksrc_dirname == linksrc, (
                    "Logic bomb!  tar ball "
                    "path {} does not contain {}".format(tb, linksrc)
                )

                idxctx.logger.info("Starting {} (size {:d})", tb, size)

                ptb = None
                try:
                    # "Open" the tar ball represented by the tar ball object
                    idxctx.logger.debug("open tar ball")
                    ptb = PbenchTarBall(
                        idxctx,
                        os.path.realpath(tb),
                        tmpdir,
                        os.path.join(INCOMING_rp, controller),
                    )

                    # Construct the generator for emitting all actions.  The
                    # `idxctx` dictionary is passed along to each generator so
                    # that it can add its context for error handling to the
                    # list.
                    idxctx.logger.debug("generator setup")
                    if options.index_tool_data:
                        actions = ptb.mk_tool_data_actions()
                    else:
                        actions = ptb.make_all_actions()

                    # File name for containing all indexing errors that
                    # can't/won't be retried.
                    with open(ie_filename, "w") as fp:
                        idxctx.logger.debug("begin indexing")
                        es_res = es_index(
                            idxctx.es, actions, fp, idxctx.logger, idxctx._dbg
                        )
                except UnsupportedTarballFormat as e:
                    idxctx.logger.warning("Unsupported tar ball format: {}", e)
                    tb_res = 4
                except BadDate as e:
                    idxctx.logger.warning("Bad Date: {!r}", e)
                    tb_res = 5
                except _filenotfounderror as e:
                    idxctx.logger.warning("No such file: {}", e)
                    tb_res = 6
                except BadMDLogFormat as e:
                    idxctx.logger.warning(
                        "The metadata.log file is curdled in" " tar ball: {}", e
                    )
                    tb_res = 7
                except SosreportHostname as e:
                    idxctx.logger.warning("Bad hostname in sosreport: {}", e)
                    tb_res = 10
                except tarfile.TarError as e:
                    idxctx.logger.error(
                        "Can't unpack tar ball into {}: {}", ptb.extracted_root, e
                    )
                    tb_res = 11
                except Exception as e:
                    idxctx.logger.exception("Other indexing error: {}", e)
                    tb_res = 12
                else:
                    beg, end, successes, duplicates, failures, retries = es_res
                    idxctx.logger.info(
                        "done indexing (start ts: {}, end ts: {}, duration:"
                        " {:.2f}s, successes: {:d}, duplicates: {:d},"
                        " failures: {:d}, retries: {:d})",
                        tstos(beg),
                        tstos(end),
                        end - beg,
                        successes,
                        duplicates,
                        failures,
                        retries,
                    )
                    tb_res = 1 if failures > 0 else 0
                try:
                    ie_len = os.path.getsize(ie_filename)
                except _filenotfounderror:
                    # Above operation never made it to actual indexing, ignore.
                    pass
                except Exception:
                    idxctx.logger.exception(
                        "Unexpected error handling" " indexing errors file: {}",
                        ie_filename,
                    )
                else:
                    # Success fetching indexing error file size.
                    if ie_len > len(tb) + 1:
                        try:
                            report.post_status(tstos(end), "errors", ie_filename)
                        except Exception:
                            idxctx.logger.exception(
                                "Unexpected error issuing"
                                " report status with errors: {}",
                                ie_filename,
                            )
                finally:
                    # Unconditionally remove the indexing errors file.
                    try:
                        os.remove(ie_filename)
                    except Exception:
                        pass
                # Distinguish failure cases, so we can retry the indexing
                # easily if possible.  Different `linkerrdest` directories for
                # different failures; the rest are going to end up in
                # `linkerrdest` for later retry.
                controller_path = os.path.dirname(linksrc_dir)

                if tb_res == 0:
                    idxctx.logger.info(
                        "{}: {}/{}: success",
                        idxctx.TS,
                        os.path.basename(controller_path),
                        os.path.basename(tb),
                    )
                    # Success
                    with open(indexed, "a") as fp:
                        print(tb, file=fp)
                    rename_tb_link(
                        tb, os.path.join(controller_path, linkdest), idxctx.logger
                    )
                elif tb_res == 1:
                    idxctx.logger.warning(
                        "{}: index failures encountered on {}", idxctx.TS, tb
                    )
                    with open(erred, "a") as fp:
                        print(tb, file=fp)
                    rename_tb_link(
                        tb,
                        os.path.join(controller_path, "{}.1".format(linkerrdest)),
                        idxctx.logger,
                    )
                elif tb_res in (2, 3):
                    assert False, (
                        "Logic Bomb!  Unexpected tar ball handling "
                        "result status {:d} for tar ball {}".format(tb_res, tb)
                    )
                elif tb_res >= 4 or res <= 11:
                    # # Quietly skip these errors
                    with open(skipped, "a") as fp:
                        print(tb, file=fp)
                    rename_tb_link(
                        tb,
                        os.path.join(
                            controller_path, "{}.{:d}".format(linkerrdest, tb_res)
                        ),
                        idxctx.logger,
                    )
                else:
                    idxctx.logger.error(
                        "{}: index error {:d} encountered on {}", idxctx.TS, tb_res, tb
                    )
                    with open(erred, "a") as fp:
                        print(tb, file=fp)
                    rename_tb_link(
                        tb, os.path.join(controller_path, linkerrdest), idxctx.logger
                    )
                idxctx.logger.info("Finished {} (size {:d})", tb, size)
        except Exception:
            idxctx.logger.exception("Unexpected setup error")
            res = 12
        else:
            # No exceptions while processing tar ball, success.
            res = 0
        finally:
            if idxctx:
                idxctx.dump_opctx()
            idxctx.logger.debug("stopped processing list of tar balls")

            idx = _count_lines(indexed)
            skp = _count_lines(skipped)
            err = _count_lines(erred)

            idxctx.logger.info(
                "{}.{}: indexed {:d} (skipped {:d}) results," " {:d} errors",
                name,
                idxctx.TS,
                idx,
                skp,
                err,
            )

            if err > 0:
                if skp > 0:
                    subj = (
                        "{}.{} - Indexed {:d} results, skipped {:d}"
                        " results, w/ {:d} errors".format(
                            name, idxctx.TS, idx, skp, err
                        )
                    )
                else:
                    subj = "{}.{} - Indexed {:d} results, w/ {:d}" " errors".format(
                        name, idxctx.TS, idx, err
                    )
            else:
                if skp > 0:
                    subj = (
                        "{}.{} - Indexed {:d} results, skipped {:d}"
                        " results".format(name, idxctx.TS, idx, skp)
                    )
                else:
                    subj = "{}.{} - Indexed {:d} results".format(name, idxctx.TS, idx)

            report_fname = os.path.join(tmpdir, "{}.{}.report".format(name, idxctx.TS))
            with open(report_fname, "w") as fp:
                print(subj, file=fp)
                if idx > 0:
                    print("\nIndexed Results\n===============", file=fp)
                    with open(indexed) as ifp:
                        for line in ifp:
                            print(line, file=fp)
                if err > 0:
                    print(
                        "\nResults producing errors" "\n========================",
                        file=fp,
                    )
                    with open(erred) as efp:
                        for line in efp:
                            print(line, file=fp)
                if skp > 0:
                    print("\nSkipped Results\n===============", file=fp)
                    with open(skipped) as sfp:
                        for line in sfp:
                            print(line, file=fp)
            try:
                report.post_status(tstos(idxctx.time()), "status", report_fname)
            except Exception:
                pass

    return res


###########################################################################
# Options handling
if __name__ == "__main__":
    run_name = os.path.basename(sys.argv[0])
    run_name = run_name if run_name[-3:] != ".py" else run_name[:-3]
    if run_name not in ("pbench-index",):
        print("unexpected command file name: {}".format(run_name), file=sys.stderr)
        sys.exit(1)
    parser = ArgumentParser(
        "Usage: {} [--config <path-to-config-file>] [--dump-index-patterns]"
        " [--dump_templates]".format(run_name)
    )
    parser.add_argument("-C", "--config", dest="cfg_name", help="Specify config file")
    parser.set_defaults(cfg_name=os.environ.get("_PBENCH_SERVER_CONFIG"))
    parser.add_argument(
        "-I",
        "--dump-index-patterns",
        action="store_true",
        dest="dump_index_patterns",
        help="Emit a list of index patterns used",
    )
    parser.add_argument(
        "-Q",
        "--dump-templates",
        action="store_true",
        dest="dump_templates",
        help="Emit the full JSON document for each index template used",
    )
    parser.set_defaults(index_tool_data=False)
    parser.add_argument(
        "-T",
        "--tool-data",
        action="store_true",
        dest="index_tool_data",
        help="Only index tool data, assumes run data already exists",
    )
    parsed = parser.parse_args()
    status = main(parsed, run_name)
    sys.exit(status)
