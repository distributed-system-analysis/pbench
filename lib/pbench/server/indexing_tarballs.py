"""Initialising Indexing class"""

import os
import glob
import signal
import tempfile
from pathlib import Path
from collections import deque

from pbench.common.exceptions import (
    BadDate,
    UnsupportedTarballFormat,
    BadMDLogFormat,
    TemplateError,
)
from pbench.server import tstos
from pbench.server.indexer import (
    PbenchTarBall,
    es_index,
    VERSION,
)
from pbench.server.database.models.tracker import (
    Dataset,
    States,
    Metadata,
    DatasetNotFound,
    DatasetTransitionError,
)
from pbench.server.report import Report
from pbench.server.utils import rename_tb_link, quarantine


class SigIntException(Exception):
    pass


def sigint_handler(*args):
    raise SigIntException()


class SigTermException(Exception):
    pass


class ErrorCode:
    def __init__(self, name, value, tarball_error, message):
        self.name = name
        self.value = value
        self.success = value == 0
        self.tarball_error = tarball_error
        self.message = message


class Errors:
    def __init__(self, *codes):
        self.errors = {code.name: code for code in codes}

    def __getitem__(self, key):
        return self.errors[key]


def _count_lines(fname):
    """Simple method to count the lines of a file.
    """
    try:
        with open(fname, "r") as fp:
            cnt = sum(1 for line in fp)
    except FileNotFoundError:
        cnt = 0
    return cnt


class Index:
    """ class used to collect tarballs and index them

        Status codes used by es_index and the error below are defined to
        maintain compatibility with the previous code base when pbench-index
        was a bash script.
    """

    error_code = Errors(
        ErrorCode("OK", 0, None, "Successful completion"),
        ErrorCode("OP_ERROR", 1, False, "Operational error while indexing"),
        ErrorCode("CFG_ERROR", 2, False, "Configuration file not specified"),
        ErrorCode("BAD_CFG", 3, False, "Bad configuration file"),
        ErrorCode(
            "TB_META_ABSENT", 4, True, "Tar ball does not contain a metadata.log file",
        ),
        ErrorCode("BAD_DATE", 5, True, "Bad start run date value encountered"),
        ErrorCode("FILE_NOT_FOUND_ERROR", 6, True, "File Not Found error"),
        ErrorCode("BAD_METADATA", 7, True, "Bad metadata.log file encountered"),
        ErrorCode(
            "MAPPING_ERROR",
            8,
            False,
            "Error reading a mapping file for Elasticsearch templates",
        ),
        ErrorCode(
            "TEMPLATE_CREATION_ERROR",
            9,
            False,
            "Error creating one of the Elasticsearch templates",
        ),
        ErrorCode("GENERIC_ERROR", 12, False, "Unexpected error encountered"),
    )

    def __init__(self, name, options, idxctx, incoming, archive, qdir):

        self.options = options
        _re_idx = "RE-" if options.re_index else ""
        if options.index_tool_data:
            # The link source and destination for the operation of this script
            # when it only indexes tool data.
            self.linksrc = "TO-INDEX-TOOL"
            self.linkdest = "INDEXED"
        else:
            # The link source and destination for the operation of this script
            # when it indexes run, table-of-contents, and result data.
            self.linksrc = f"TO-{_re_idx}INDEX"
            self.linkdest = "TO-INDEX-TOOL"
        # We only ever use a symlink'd error destination for indexing
        # problems.
        self.linkerrdest = "WONT-INDEX"
        self.idxctx = idxctx
        self.incoming = incoming
        self.name = name
        self.archive = archive
        self.qdir = qdir

    def collect_tb(self):
        """ Collect tarballs that needs indexing"""

        # find -L $ARCHIVE/*/$linksrc -name '*.tar.xz' -printf "%s\t%p\n" 2>/dev/null | sort -n > $list
        tarballs = []
        idxctx = self.idxctx
        error_code = self.error_code
        try:
            tb_glob = os.path.join(self.archive, "*", self.linksrc, "*.tar.xz")
            for tb in glob.iglob(tb_glob):
                try:
                    rp = Path(tb).resolve(strict=True)
                except OSError:
                    idxctx.logger.warning("{} does not resolve to a real path", tb)
                    quarantine(self.qdir, idxctx.logger, tb)
                    continue
                controller_path = rp.parent
                controller = controller_path.name
                archive_path = controller_path.parent
                if str(archive_path) != str(self.archive):
                    idxctx.logger.warning(
                        "For tar ball {}, original home is not {}", tb, self.archive
                    )
                    quarantine(self.qdir, idxctx.logger, tb)
                    continue
                if not Path(f"{rp}.md5").is_file():
                    idxctx.logger.warning("Missing .md5 file for {}", tb)
                    quarantine(self.qdir, idxctx.logger, tb)
                    # Audit should pick up missing .md5 file in ARCHIVE directory.
                    continue
                try:
                    # get size
                    size = rp.stat().st_size
                except OSError:
                    idxctx.logger.warning("Could not fetch tar ball size for {}", tb)
                    quarantine(self.qdir, idxctx.logger, tb)
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
                "{} generating list of tar balls to process",
                error_code["GENERIC_ERROR"].message,
            )
            # tuple to return the status and return value
            return (error_code["GENERIC_ERROR"].value, [])
        else:
            if not tarballs:
                idxctx.logger.info("No tar balls found that need processing")

        return (error_code["OK"].value, sorted(tarballs))

    def emit_error(self, logger_method, error, exception):
        """Helper method to write a log message in a standard format from an error code

            Args
                logger_method -- Reference to a method of a Python logger object,
                                like idxctx.logger.warning
                error -- An error code name from the Errors collection, like "OK"
                exception -- the original exception leading to the error

            Returns
                Relevant error_code object

            Although all log messages will appear to have originated from this method,
            the origin can easily be identified from the error code value, and this
            interface provides simplicity and consistency.
        """
        ec = self.error_code[error]
        logger_method("{}: {}", ec.message, exception)
        return ec

    def process_tb(self, tarballs):
        """Process Tarballs For Indexing and creates report

            "tarballs" - List of tarball, it is the second value of
                the tuple returned by collect_tb() """
        res = 0
        idxctx = self.idxctx
        error_code = self.error_code

        tb_deque = deque(sorted(tarballs))

        # At this point, tarballs contains a list of tar balls sorted by size
        # that were available as symlinks in the various 'linksrc' directories.
        idxctx.logger.debug("Preparing to index {:d} tar balls", len(tb_deque))

        try:
            # Now that we are ready to begin the actual indexing step, ensure we
            # have the proper index templates in place.
            idxctx.logger.debug("update_templates [start]")
            idxctx.templates.update_templates(idxctx.es)
        except TemplateError as e:
            res = self.emit_error(idxctx.logger.error, "TEMPLATE_CREATION_ERROR", e)
        except SigTermException:
            # Re-raise a SIGTERM to avoid it being lumped in with general
            # exception handling below.
            raise
        except Exception:
            idxctx.logger.exception(
                "update_templates [end]: Unexpected template" " processing error"
            )
            res = error_code["GENERIC_ERROR"]
        else:
            idxctx.logger.debug("update_templates [end]")
            res = error_code["OK"]

        if not res.success:
            # Exit early if we encounter any errors.
            return res.value

        report = Report(
            idxctx.config,
            self.name,
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
            return error_code["GENERIC_ERROR"].value
        else:
            idxctx.set_tracking_id(tracking_id)

        with tempfile.TemporaryDirectory(
            prefix=f"{self.name}.", dir=idxctx.config.TMP
        ) as tmpdir:
            idxctx.logger.debug("start processing list of tar balls")
            tb_list = Path(tmpdir, f"{self.name}.{idxctx.TS}.list")
            try:
                with tb_list.open(mode="w") as lfp:
                    # Write out all the tar balls we are processing so external
                    # viewers can follow along from home.
                    for size, controller, tb in tarballs:
                        print(f"{size:20d} {controller} {tb}", file=lfp)

                indexed = Path(tmpdir, f"{self.name}.{idxctx.TS}.indexed")
                erred = Path(tmpdir, f"{self.name}.{idxctx.TS}.erred")
                skipped = Path(tmpdir, f"{self.name}.{idxctx.TS}.skipped")
                ie_filepath = Path(
                    tmpdir, f"{self.name}.{idxctx.TS}.indexing-errors.json"
                )

                # We use a list object here so that when we close over this
                # variable in the handler, the list object will be closed over,
                # but not its contents.
                sigquit_interrupt = [False]

                def sigquit_handler(*args):
                    sigquit_interrupt[0] = True

                sighup_interrupt = [False]

                def sighup_handler(*args):
                    sighup_interrupt[0] = True

                signal.signal(signal.SIGQUIT, sigquit_handler)
                signal.signal(signal.SIGHUP, sighup_handler)
                count_processed_tb = 0

                try:
                    while len(tb_deque) > 0:
                        size, controller, tb = tb_deque.popleft()
                        # Sanity check source tar ball path
                        linksrc_dir = Path(tb).parent
                        linksrc_dirname = linksrc_dir.name
                        count_processed_tb += 1
                        assert linksrc_dirname == self.linksrc, (
                            f"Logic bomb!  tar ball "
                            f"path {tb} does not contain {self.linksrc}"
                        )

                        idxctx.logger.info("Starting {} (size {:d})", tb, size)
                        dataset = None
                        ptb = None
                        username = None
                        try:
                            path = os.path.realpath(tb)

                            try:
                                dataset = Dataset.attach(
                                    path=path, state=States.INDEXING,
                                )
                            except DatasetNotFound:
                                idxctx.logger.warn(
                                    "Unable to locate Dataset {}", path,
                                )
                            except DatasetTransitionError as e:
                                # TODO: This means the Dataset is known, but not in a
                                # state where we'd expect to be indexing it. So what do
                                # we do with it? (Note: this is where an audit log will
                                # be handy; i.e., how did we get here?) For now, just
                                # let it go.
                                idxctx.logger.warn(
                                    "Unable to advance dataset state: {}", str(e)
                                )
                            else:
                                username = dataset.owner

                            # "Open" the tar ball represented by the tar ball object
                            idxctx.logger.debug("open tar ball")
                            ptb = PbenchTarBall(
                                idxctx,
                                username,
                                path,
                                tmpdir,
                                Path(self.incoming, controller),
                            )

                            # Construct the generator for emitting all actions.  The
                            # `idxctx` dictionary is passed along to each generator so
                            # that it can add its context for error handling to the
                            # list.
                            idxctx.logger.debug("generator setup")
                            if self.options.index_tool_data:
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
                                        idxctx.es,
                                        actions,
                                        fp,
                                        idxctx.logger,
                                        idxctx._dbg,
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
                            tb_res = self.emit_error(
                                idxctx.logger.warning, "TB_META_ABSENT", e
                            )
                        except BadDate as e:
                            tb_res = self.emit_error(
                                idxctx.logger.warning, "BAD_DATE", e
                            )
                        except FileNotFoundError as e:
                            tb_res = self.emit_error(
                                idxctx.logger.warning, "FILE_NOT_FOUND_ERROR", e
                            )
                        except BadMDLogFormat as e:
                            tb_res = self.emit_error(
                                idxctx.logger.warning, "BAD_METADATA", e
                            )
                        except SigTermException:
                            idxctx.logger.exception(
                                "Indexing interrupted by SIGTERM, terminating"
                            )
                            break
                        except Exception as e:
                            tb_res = self.emit_error(
                                idxctx.logger.exception, "GENERIC_ERROR", e
                            )
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
                            tb_res = error_code["OP_ERROR" if failures > 0 else "OK"]
                        finally:
                            if dataset:
                                try:
                                    dataset.advance(
                                        States.INDEXED
                                        if tb_res.success
                                        else States.QUARANTINED
                                    )
                                    Metadata.remove(dataset, Metadata.REINDEX)
                                except DatasetTransitionError:
                                    idxctx.logger.exception("Dataset state error")

                        try:
                            ie_len = ie_filepath.stat().st_size
                        except FileNotFoundError:
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
                                    report.post_status(
                                        tstos(end), "errors", ie_filepath
                                    )
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

                        if tb_res is error_code["OK"]:
                            idxctx.logger.info(
                                "{}: {}/{}: success",
                                idxctx.TS,
                                controller_path.name,
                                os.path.basename(tb),
                            )
                            # Success
                            with indexed.open(mode="a") as fp:
                                print(tb, file=fp)
                            rename_tb_link(
                                tb, Path(controller_path, self.linkdest), idxctx.logger
                            )
                        elif tb_res is error_code["OP_ERROR"]:
                            idxctx.logger.warning(
                                "{}: index failures encountered on {}", idxctx.TS, tb
                            )
                            with erred.open(mode="a") as fp:
                                print(tb, file=fp)
                            rename_tb_link(
                                tb,
                                Path(controller_path, f"{self.linkerrdest}.1"),
                                idxctx.logger,
                            )
                        elif tb_res in (error_code["CFG_ERROR"], error_code["BAD_CFG"]):
                            assert False, (
                                f"Logic Bomb!  Unexpected tar ball handling "
                                f"result status {tb_res.value:d} for tar ball {tb}"
                            )
                        elif tb_res.tarball_error:
                            # # Quietly skip these errors
                            with skipped.open(mode="a") as fp:
                                print(tb, file=fp)
                            rename_tb_link(
                                tb,
                                Path(
                                    controller_path,
                                    f"{self.linkerrdest}.{tb_res.value:d}",
                                ),
                                idxctx.logger,
                            )
                        else:
                            idxctx.logger.error(
                                "{}: index error {:d} encountered on {}",
                                idxctx.TS,
                                tb_res.value,
                                tb,
                            )
                            with erred.open(mode="a") as fp:
                                print(tb, file=fp)
                            rename_tb_link(
                                tb,
                                Path(controller_path, self.linkerrdest),
                                idxctx.logger,
                            )
                        idxctx.logger.info(
                            "Finished{} {} (size {:d})",
                            "[SIGQUIT]" if sigquit_interrupt[0] else "",
                            tb,
                            size,
                        )

                        if sigquit_interrupt[0]:
                            break
                        if sighup_interrupt[0]:
                            status, new_tb = self.collect_tb()
                            if status == 0:
                                if not set(new_tb).issuperset(tb_deque):
                                    idxctx.logger.info(
                                        "Tarballs supposed to be in 'TO-INDEX' are no longer present",
                                        set(tb_deque).difference(new_tb),
                                    )
                                tb_deque = deque(sorted(new_tb))
                            idxctx.logger.info(
                                "SIGHUP status (Current tar ball indexed: ({}), Remaining: {}, Completed: {}, Errors_encountered: {}, Status: {})",
                                Path(tb).name,
                                len(tb_deque),
                                count_processed_tb,
                                _count_lines(erred),
                                tb_res,
                            )
                            sighup_interrupt[0] = False
                            continue
                except SigTermException:
                    idxctx.logger.exception(
                        "Indexing interrupted by SIGQUIT, stop processing tarballs"
                    )
                finally:
                    # Turn off the SIGQUIT and SIGHUP handler when not indexing.
                    signal.signal(signal.SIGQUIT, signal.SIG_IGN)
                    signal.signal(signal.SIGHUP, signal.SIG_IGN)
            except SigTermException:
                # Re-raise a SIGTERM to avoid it being lumped in with general
                # exception handling below.
                raise
            except Exception:
                idxctx.logger.exception(error_code["GENERIC_ERROR"].message)
                res = error_code["GENERIC_ERROR"]
            else:
                # No exceptions while processing tar ball, success.
                res = error_code["OK"]
            finally:
                if idxctx:
                    idxctx.dump_opctx()
                idxctx.logger.debug("stopped processing list of tar balls")

                idx = _count_lines(indexed)
                skp = _count_lines(skipped)
                err = _count_lines(erred)

                idxctx.logger.info(
                    "{}.{}: indexed {:d} (skipped {:d}) results," " {:d} errors",
                    self.name,
                    idxctx.TS,
                    idx,
                    skp,
                    err,
                )

                if err > 0:
                    if skp > 0:
                        subj = (
                            f"{self.name}.{idxctx.TS} - Indexed {idx:d} results, skipped {skp:d}"
                            f" results, w/ {err:d} errors"
                        )
                    else:
                        subj = (
                            f"{self.name}.{idxctx.TS} - Indexed {idx:d} results, w/ {err:d}"
                            " errors"
                        )
                else:
                    if skp > 0:
                        subj = f"{self.name}.{idxctx.TS} - Indexed {idx:d} results, skipped {skp:d} results"
                    else:
                        subj = f"{self.name}.{idxctx.TS} - Indexed {idx:d} results"

                report_fname = Path(tmpdir, f"{self.name}.{idxctx.TS}.report")
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

        return res.value
