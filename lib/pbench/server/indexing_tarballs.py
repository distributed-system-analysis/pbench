"""Initialising Indexing class"""

from argparse import Namespace
from collections import deque
import os
from pathlib import Path
import signal
import tempfile
from typing import Callable, List, NamedTuple, Optional, Tuple

from pbench.common.exceptions import (
    BadDate,
    BadMDLogFormat,
    TemplateError,
    UnsupportedTarballFormat,
)
from pbench.server import OperationCode, tstos
from pbench.server.cache_manager import CacheManager, LockRef, Tarball
from pbench.server.database.models.audit import Audit, AuditStatus
from pbench.server.database.models.datasets import (
    Dataset,
    DatasetError,
    Metadata,
    OperationName,
    OperationState,
)
from pbench.server.database.models.index_map import IndexMap
from pbench.server.indexer import es_index, IdxContext, PbenchTarBall, VERSION
from pbench.server.report import Report
from pbench.server.sync import Sync


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

    def __repr__(self) -> str:
        return (
            f"ErrorCode<name={self.name}, value={self.value}, message={self.message!r}>"
        )


class Errors:
    def __init__(self, *codes):
        self.errors = {code.name: code for code in codes}

    def __getitem__(self, key):
        return self.errors[key]


def _count_lines(fname):
    """Simple method to count the lines of a file."""
    try:
        with open(fname, "r") as fp:
            cnt = sum(1 for line in fp)
    except FileNotFoundError:
        cnt = 0
    return cnt


class TarballData(NamedTuple):
    """
    Maintain data about a tarball. We put the tarball size first:
    this is a sort key to ensure that we tackle smaller tarballs
    first rather than stick them behind larger tarballs which are
    presumably slower to index.
    """

    size: int
    dataset: Dataset
    tarball: str


class Index:
    """class used to identify and process tarballs selected for indexing.

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
            "TB_META_ABSENT",
            4,
            True,
            "Tar ball does not contain a metadata.log file",
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

    def __init__(self, name: str, options: Namespace, idxctx: IdxContext):

        # pbench-index command options
        self.options: Namespace = options
        if options.index_tool_data:
            # The link source and destination for the operation of this script
            # when it only indexes tool data.
            self.operation = OperationName.TOOLINDEX
            self.enabled = None
        else:
            # The link source and destination for the operation of this script
            # when it indexes run, table-of-contents, and result data.
            self.operation = (
                OperationName.REINDEX if options.re_index else OperationName.INDEX
            )
            self.enabled = [OperationName.TOOLINDEX]

        # indexing context
        self.idxctx: IdxContext = idxctx

        # Index context name
        self.name: str = name

        # An Elasticsearch status Report object
        self.report: Optional[Report] = None

        # We'll use a cache manager instance to find the INCOMING directory for the
        # unpacked tarballs.
        self.cache_manager: CacheManager = CacheManager(idxctx.config, idxctx.logger)

        # Manage synchronization between components
        self.sync: Sync = Sync(idxctx.logger, self.operation)  # Build a sync object

    def collect_tb(self) -> Tuple[int, List[TarballData]]:
        """Collect tarballs that need indexing

        This looks for Datasets marked to require indexing, and returns a list
        of indexing candidates.

        The list is sorted by the size of the tarballs, so that smaller
        datasets (presumptively faster to index) don't get stalled behind
        large ones.

        Returns:
            A tuple consisting of an error number from the 'error_code'
            attribute and a list of tarball descriptions.
        """

        tarballs: List[TarballData] = []
        idxctx = self.idxctx
        error_code = self.error_code
        try:
            for dataset in self.sync.next():
                tb = Metadata.getvalue(dataset, Metadata.TARBALL_PATH)
                if not tb:
                    self.sync.error(dataset, "Dataset does not have a tarball-path")
                    continue

                try:
                    # get size
                    size = os.stat(tb).st_size
                except OSError as e:
                    self.sync.error(dataset, f"Could not fetch tarball size: {e!s}")
                    continue
                else:
                    tarballs.append(TarballData(dataset=dataset, tarball=tb, size=size))
        except SigTermException:
            # Re-raise a SIGTERM to avoid it being lumped in with general
            # exception handling below.
            raise
        except Exception as e:
            idxctx.logger.error(
                "{} generating list of tar balls to process: {}",
                error_code["GENERIC_ERROR"].message,
                str(e),
            )
            # Return catch-all error and no tarballs
            return (error_code["GENERIC_ERROR"].value, [])
        else:
            if not tarballs:
                idxctx.logger.info("No tar balls found that need processing")

        return (error_code["OK"].value, sorted(tarballs, key=lambda t: t.size))

    def emit_error(
        self, logger_method: Callable, error: str, exception: Exception
    ) -> ErrorCode:
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

    def load_templates(self) -> ErrorCode:
        """Load Elasticsearch templates using the template management class,
        and create an Elasticsearch server-report document on the indexing
        process.

        Returns:
            An ErrorCode instance
        """
        idxctx = self.idxctx
        error_code = self.error_code
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
            return res

        self.report = Report(
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
            tracking_id = self.report.post_status(tstos(), "start")
        except SigTermException:
            # Re-raise a SIGTERM to avoid it being lumped in with general
            # exception handling below.
            raise
        except Exception:
            idxctx.logger.error("Failed to post initial report status")
            return error_code["GENERIC_ERROR"]
        else:
            idxctx.set_tracking_id(tracking_id)

        return res

    def process_tb(self, tarballs: List[TarballData]) -> int:
        """Process Tarballs For Indexing and create a summary report.

        Args:
            tarballs:   List of tarball information tuples

        Returns:
            status code
        """

        idxctx = self.idxctx
        error_code = self.error_code

        tb_deque = deque(tarballs)

        res = self.load_templates()
        if not res.success:
            idxctx.logger.info("Load templates {!r}", res)
            return res.value

        idxctx.logger.debug("Preparing to index {:d} tar balls", len(tb_deque))

        with tempfile.TemporaryDirectory(
            prefix=f"{self.name}.", dir=idxctx.config.TMP
        ) as tmpdir:
            idxctx.logger.debug("start processing list of tar balls")
            tb_list = Path(tmpdir, f"{self.name}.{idxctx.TS}.list")
            try:
                with tb_list.open(mode="w") as lfp:
                    # Write out all the tar balls we are processing so external
                    # viewers can follow along from home.
                    for size, dataset, tb in tarballs:
                        print(f"{size:20d} {dataset.name} {tb}", file=lfp)

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
                        tbinfo: TarballData = tb_deque.popleft()
                        size = tbinfo.size
                        dataset = tbinfo.dataset
                        tb = tbinfo.tarball
                        count_processed_tb += 1

                        idxctx.logger.info("Starting {} (size {:d})", tb, size)
                        audit = None
                        ptb = None
                        tarobj: Optional[Tarball] = None
                        tb_res = error_code["OK"]
                        lock = None
                        try:
                            # We need the fully unpacked cache tree to index it
                            try:
                                tarobj = self.cache_manager.find_dataset(
                                    dataset.resource_id
                                )
                                lock = LockRef(tarobj.lock).acquire()
                                tarobj.get_results(lock)
                            except Exception as e:
                                self.sync.error(
                                    dataset,
                                    f"Unable to unpack dataset: {e!s}",
                                )
                                if lock:
                                    lock.release()
                                continue

                            audit = Audit.create(
                                operation=OperationCode.UPDATE,
                                name="index",
                                status=AuditStatus.BEGIN,
                                user_name=Audit.BACKGROUND_USER,
                                dataset=dataset,
                            )

                            # "Open" the tar ball represented by the tar ball object
                            idxctx.logger.debug("open tar ball")
                            ptb = PbenchTarBall(idxctx, dataset, tmpdir, tarobj)

                            # Construct the generator for emitting all actions.
                            # The `idxctx` dictionary is passed along to each
                            # generator so that it can add its context for
                            # error handling to the list.
                            idxctx.logger.debug("generator setup")
                            if self.options.index_tool_data:
                                actions = ptb.mk_tool_data_actions()
                            else:
                                actions = ptb.make_all_actions()

                            # Create a file where the pyesbulk package will
                            # record all indexing errors that can't/won't be
                            # retried.
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
                            if tb_res.success:
                                try:

                                    # Because we're on the `finally` path, we
                                    # can get here without a PbenchTarBall
                                    # object, so don't try to write an index
                                    # map if there is none.
                                    if ptb:
                                        # A pbench-index --tool-data follows a
                                        # pbench-index and generates only the
                                        # tool-specific documents: we want to
                                        # merge that with the existing document
                                        # map. On the other hand, a re-index
                                        # should replace the entire index. We
                                        # accomplish this by overwriting each
                                        # duplicate index key separately.
                                        try:
                                            if IndexMap.exists(dataset):
                                                IndexMap.merge(dataset, ptb.index_map)
                                            else:
                                                IndexMap.create(dataset, ptb.index_map)
                                        except Exception as e:
                                            idxctx.logger.exception(
                                                "Unexpected Metadata error on {}: {}",
                                                ptb.tbname,
                                                e,
                                            )
                                except DatasetError as e:
                                    idxctx.logger.exception(
                                        "Dataset error on {}: {}", ptb.tbname, e
                                    )
                                except Exception as e:
                                    idxctx.logger.exception(
                                        "Unexpected error on {}: {}", ptb.tbname, e
                                    )
                            if audit:
                                doneness = AuditStatus.SUCCESS
                                attributes = None

                                # TODO: can we categorize anything as "WARNING"?
                                if tb_res != error_code["OK"]:
                                    doneness = AuditStatus.FAILURE
                                    attributes = {"message": tb_res.message}
                                Audit.create(
                                    root=audit, status=doneness, attributes=attributes
                                )
                            if lock:
                                lock.release()
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
                                    self.report.post_status(
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
                        # easily if possible.
                        #
                        # Only if the indexing was successful do we request the
                        # next operation (tool indexing). Otherwise we record
                        # the error in the `server.errors.index` metadata and
                        # leave the dataset in INDEXING state.
                        if tb_res.success:
                            idxctx.logger.info(
                                "{}: {}: success",
                                idxctx.TS,
                                os.path.basename(tb),
                            )
                            # Success
                            with indexed.open(mode="a") as fp:
                                print(tb, file=fp)
                            self.sync.update(
                                dataset=dataset,
                                state=OperationState.OK,
                                enabled=self.enabled,
                            )
                        elif tb_res is error_code["OP_ERROR"]:
                            with erred.open(mode="a") as fp:
                                print(tb, file=fp)
                            self.sync.error(dataset, f"{tb_res.value}:{tb_res.message}")
                        elif tb_res in (error_code["CFG_ERROR"], error_code["BAD_CFG"]):
                            assert False, (
                                f"Unexpected tar ball handling "
                                f"result status {tb_res.value:d} for dataset {dataset}"
                            )
                        elif tb_res.tarball_error:
                            # # Quietly skip these errors
                            with skipped.open(mode="a") as fp:
                                print(tb, file=fp)
                            self.sync.error(dataset, f"{tb_res.value}:{tb_res.message}")
                        else:
                            with erred.open(mode="a") as fp:
                                print(tb, file=fp)
                            self.sync.error(dataset, f"{tb_res.value}:{tb_res.message}")
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
                                        "Tarballs previously marked for indexing are no longer present",
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
                # No exceptions while processing tar balls, success.
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
                    self.report.post_status(tstos(), "status", report_fname)
                except SigTermException:
                    # Re-raise a SIGTERM to avoid it being lumped in with general
                    # exception handling below.
                    raise
                except Exception:
                    pass

        return res.value
