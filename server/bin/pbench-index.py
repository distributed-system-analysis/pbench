#!/usr/bin/env python3
# -*- mode: python -*-

"""Pbench indexing driver, responsible for indexing a single pbench tar ball
into the configured Elasticsearch V1 instance.

"""

import sys
import os
import glob
import signal
import tarfile
import tempfile
from pathlib import Path
from argparse import ArgumentParser
from configparser import Error as ConfigParserError

from pbench.common.exceptions import (
    BadConfig,
    ConfigFileError,
    BadDate,
    UnsupportedTarballFormat,
    SosreportHostname,
    BadMDLogFormat,
    JsonFileError,
    TemplateError,
)
from pbench.server import tstos
from pbench.server.indexer import (
    IdxContext,
    PbenchTarBall,
    es_index,
    VERSION,
)
from pbench.server.report import Report
from pbench.server.utils import rename_tb_link, quarantine


class SigIntException(Exception):
    pass


def sigint_handler(*args):
    raise SigIntException()


class SigTermException(Exception):
    pass


def sigterm_handler(*args):
    raise SigTermException()


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

    _re_idx = "RE-" if options.re_index else ""
    if options.index_tool_data:
        # The link source and destination for the operation of this script
        # when it only indexes tool data.
        linksrc = "TO-INDEX-TOOL"
        linkdest = "INDEXED"
    else:
        # The link source and destination for the operation of this script
        # when it indexes run, table-of-contents, and result data.
        linksrc = f"TO-{_re_idx}INDEX"
        linkdest = "TO-INDEX-TOOL"
    # We only ever use a symlink'd error destination for indexing
    # problems.
    linkerrdest = "WONT-INDEX"

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

    # find -L $ARCHIVE/*/$linksrc -name '*.tar.xz' -printf "%s\t%p\n" 2>/dev/null | sort -n > $list
    tarballs = []
    try:
        tb_glob = os.path.join(ARCHIVE_rp, "*", linksrc, "*.tar.xz")
        for tb in glob.iglob(tb_glob):
            try:
                rp = Path(tb).resolve(strict=True)
            except OSError:
                idxctx.logger.warning("{} does not resolve to a real path", tb)
                quarantine(qdir, idxctx.logger, tb)
                continue
            controller_path = rp.parent
            controller = controller_path.name
            archive_path = controller_path.parent
            if str(archive_path) != str(ARCHIVE_rp):
                idxctx.logger.warning(
                    "For tar ball {}, original home is not {}", tb, ARCHIVE_rp
                )
                quarantine(qdir, idxctx.logger, tb)
                continue
            if not Path(f"{rp}.md5").is_file():
                idxctx.logger.warning("Missing .md5 file for {}", tb)
                quarantine(qdir, idxctx.logger, tb)
                # Audit should pick up missing .md5 file in ARCHIVE directory.
                continue
            try:
                # get size
                size = rp.stat().st_size
            except OSError:
                idxctx.logger.warning("Could not fetch tar ball size for {}", tb)
                quarantine(qdir, idxctx.logger, tb)
                # Audit should pick up missing .md5 file in ARCHIVE directory.
                continue
            else:
                tarballs.append((size, controller, tb))
    except SigTermException:
        # Re-raise a SIGTERM to avoid it being lumped in with general
        # exception handling below.
        raise
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
    except SigTermException:
        # Re-raise a SIGTERM to avoid it being lumped in with general
        # exception handling below.
        raise
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
    except SigTermException:
        # Re-raise a SIGTERM to avoid it being lumped in with general
        # exception handling below.
        raise
    except Exception:
        idxctx.logger.error("Failed to post initial report status")
        return 12
    else:
        idxctx.set_tracking_id(tracking_id)

    with tempfile.TemporaryDirectory(
        prefix=f"{name}.", dir=idxctx.config.TMP
    ) as tmpdir:
        idxctx.logger.debug("start processing list of tar balls")
        tb_list = Path(tmpdir, f"{name}.{idxctx.TS}.list")
        try:
            with tb_list.open(mode="w") as lfp:
                # Write out all the tar balls we are processing so external
                # viewers can follow along from home.
                for size, controller, tb in tarballs:
                    print(f"{size:20d} {controller} {tb}", file=lfp)

            indexed = Path(tmpdir, f"{name}.{idxctx.TS}.indexed")
            erred = Path(tmpdir, f"{name}.{idxctx.TS}.erred")
            skipped = Path(tmpdir, f"{name}.{idxctx.TS}.skipped")
            ie_filepath = Path(tmpdir, f"{name}.{idxctx.TS}.indexing-errors.json")

            # We use a list object here so that when we close over this
            # variable in the handler, the list object will be closed over,
            # but not its contents.
            sigquit_interrupt = [False]

            def sigquit_handler(*args):
                sigquit_interrupt[0] = True

            signal.signal(signal.SIGQUIT, sigquit_handler)

            for size, controller, tb in tarballs:
                # Sanity check source tar ball path
                linksrc_dir = Path(tb).parent
                linksrc_dirname = linksrc_dir.name
                assert linksrc_dirname == linksrc, (
                    f"Logic bomb!  tar ball " f"path {tb} does not contain {linksrc}"
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
                        Path(INCOMING_rp, controller),
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
                    with ie_filepath.open(mode="w") as fp:
                        idxctx.logger.debug("begin indexing")
                        try:
                            signal.signal(signal.SIGINT, sigint_handler)
                            es_res = es_index(
                                idxctx.es, actions, fp, idxctx.logger, idxctx._dbg
                            )
                        except SigIntException:
                            idxctx.logger.exception(
                                "Indexing interrupted by SIGINT, continuing to next tarball"
                            )
                            continue
                        finally:
                            # Turn off the SIGINT handler when not indexing.
                            signal.signal(signal.SIGINT, signal.SIG_IGN)
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
                except SigTermException:
                    idxctx.logger.exception(
                        "Indexing interrupted by SIGTERM, terminating"
                    )
                    break
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
                    ie_len = ie_filepath.stat().st_size
                except _filenotfounderror:
                    # Above operation never made it to actual indexing, ignore.
                    pass
                except SigTermException:
                    # Re-raise a SIGTERM to avoid it being lumped in with
                    # general exception handling below.
                    raise
                except Exception:
                    idxctx.logger.exception(
                        "Unexpected error handling" " indexing errors file: {}",
                        ie_filepath,
                    )
                else:
                    # Success fetching indexing error file size.
                    if ie_len > len(tb) + 1:
                        try:
                            report.post_status(tstos(end), "errors", ie_filepath)
                        except Exception:
                            idxctx.logger.exception(
                                "Unexpected error issuing"
                                " report status with errors: {}",
                                ie_filepath,
                            )
                finally:
                    # Unconditionally remove the indexing errors file.
                    try:
                        os.remove(ie_filepath)
                    except SigTermException:
                        # Re-raise a SIGTERM to avoid it being lumped in with
                        # general exception handling below.
                        raise
                    except Exception:
                        pass
                # Distinguish failure cases, so we can retry the indexing
                # easily if possible.  Different `linkerrdest` directories for
                # different failures; the rest are going to end up in
                # `linkerrdest` for later retry.
                controller_path = linksrc_dir.parent

                if tb_res == 0:
                    idxctx.logger.info(
                        "{}: {}/{}: success",
                        idxctx.TS,
                        controller_path.name,
                        os.path.basename(tb),
                    )
                    # Success
                    with indexed.open(mode="a") as fp:
                        print(tb, file=fp)
                    rename_tb_link(tb, Path(controller_path, linkdest), idxctx.logger)
                elif tb_res == 1:
                    idxctx.logger.warning(
                        "{}: index failures encountered on {}", idxctx.TS, tb
                    )
                    with erred.open(mode="a") as fp:
                        print(tb, file=fp)
                    rename_tb_link(
                        tb, Path(controller_path, f"{linkerrdest}.1"), idxctx.logger,
                    )
                elif tb_res in (2, 3):
                    assert False, (
                        f"Logic Bomb!  Unexpected tar ball handling "
                        f"result status {tb_res:d} for tar ball {tb}"
                    )
                elif tb_res >= 4 or res <= 11:
                    # # Quietly skip these errors
                    with skipped.open(mode="a") as fp:
                        print(tb, file=fp)
                    rename_tb_link(
                        tb,
                        Path(controller_path, f"{linkerrdest}.{tb_res:d}"),
                        idxctx.logger,
                    )
                else:
                    idxctx.logger.error(
                        "{}: index error {:d} encountered on {}", idxctx.TS, tb_res, tb
                    )
                    with erred.open(mode="a") as fp:
                        print(tb, file=fp)
                    rename_tb_link(
                        tb, Path(controller_path, linkerrdest), idxctx.logger
                    )
                idxctx.logger.info(
                    "Finished{} {} (size {:d})",
                    "[SIGQUIT]" if sigquit_interrupt[0] else "",
                    tb,
                    size,
                )

                if sigquit_interrupt[0]:
                    break
        except SigTermException:
            # Re-raise a SIGTERM to avoid it being lumped in with general
            # exception handling below.
            raise
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
                        f"{name}.{idxctx.TS} - Indexed {idx:d} results, skipped {skp:d}"
                        f" results, w/ {err:d} errors"
                    )
                else:
                    subj = (
                        f"{name}.{idxctx.TS} - Indexed {idx:d} results, w/ {err:d}"
                        " errors"
                    )
            else:
                if skp > 0:
                    subj = f"{name}.{idxctx.TS} - Indexed {idx:d} results, skipped {skp:d} results"
                else:
                    subj = f"{name}.{idxctx.TS} - Indexed {idx:d} results"

            report_fname = Path(tmpdir, f"{name}.{idxctx.TS}.report")
            with report_fname.open(mode="w") as fp:
                print(subj, file=fp)
                if idx > 0:
                    print("\nIndexed Results\n===============", file=fp)
                    with indexed.open() as ifp:
                        for line in sorted(ifp):
                            print(line.strip(), file=fp)
                if err > 0:
                    print(
                        "\nResults producing errors" "\n========================",
                        file=fp,
                    )
                    with erred.open() as efp:
                        for line in sorted(efp):
                            print(line.strip(), file=fp)
                if skp > 0:
                    print("\nSkipped Results\n===============", file=fp)
                    with skipped.open() as sfp:
                        for line in sorted(sfp):
                            print(line.strip(), file=fp)
            try:
                report.post_status(tstos(idxctx.time()), "status", report_fname)
            except SigTermException:
                # Re-raise a SIGTERM to avoid it being lumped in with general
                # exception handling below.
                raise
            except Exception:
                pass

    return res


###########################################################################
# Options handling
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
        # to handle it cleanly once established.  We also make sure both
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
