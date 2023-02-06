from dataclasses import dataclass
from logging import Logger
from pathlib import Path
import tempfile

from pbench.server import PbenchServerConfig, timestamp
from pbench.server.cache_manager import CacheManager
from pbench.server.database.models.datasets import (
    Dataset,
    Metadata,
    OperationName,
    OperationState,
)
from pbench.server.report import Report
from pbench.server.sync import Sync


@dataclass(frozen=True)
class Target:
    dataset: Dataset
    tarball: Path


@dataclass(frozen=True)
class Results:
    total: int
    success: int


class UnpackTarballs:
    """Unpacks Tarball in the INCOMING Directory"""

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        """
        Args:
            config: PbenchServerConfig configuration object
            logger: A Pbench python Logger
        """
        self.config = config
        self.logger = logger
        self.sync = Sync(logger=logger, component=OperationName.UNPACK)
        self.cache_manager = CacheManager(config, logger)

    def unpack(self, tb: Target):
        """Encapsulate the call to the CacheManager unpacker.

        Args:
            tb: Identify the Dataset and Tarball
        """

        try:
            self.cache_manager.unpack(tb.dataset.resource_id)
        except Exception as exc:
            self.logger.error(
                "{}: Unpacking of tarball {} failed: {}",
                self.config.TS,
                tb.tarball,
                exc,
            )
            raise

    def unpack_tarballs(self, min_size: float, max_size: float) -> Results:
        """Scans for datasets ready to be unpacked, and unpacks them using the
        CacheManager.unpack() method.

        Args:
            min_size: minimum size of tarball for this Bucket
            max_size: maximum size of tarball for this Bucket

        Returns:
            Results tuple containing the counts of Total and Successful tarballs.
        """
        datasets = self.sync.next()
        tarlist: list[Target] = []
        for d in datasets:
            t = Metadata.getvalue(d, Metadata.TARBALL_PATH)
            if not t:
                self.logger.error(
                    "Dataset {} is missing a value for {}", d, Metadata.TARBALL_PATH
                )
                continue

            try:
                p = Path(t).resolve(strict=True)
                s = p.stat().st_size
            except FileNotFoundError as exc:
                self.logger.error(
                    "{}: Tarball '{}' does not resolve to a file: {}",
                    self.config.TS,
                    t,
                    exc,
                )
                continue
            except Exception:
                self.logger.exception("Unexpected exception on {}", t)
                continue

            if min_size <= s < max_size:
                self.logger.info(
                    "will unpack {} ({} >= {} < {})",
                    Dataset.stem(p),
                    min_size,
                    s,
                    max_size,
                )
                tarlist.append(Target(dataset=d, tarball=p))

        ntotal = nsuccess = 0

        for tarball in sorted(tarlist, key=lambda e: str(e.tarball)):
            try:
                ntotal += 1
                self.unpack(tarball)
                self.sync.update(
                    dataset=tarball.dataset,
                    did=OperationState.OK,
                    enabled=[OperationName.INDEX],
                )
            except Exception as e:
                self.sync.error(dataset=tarball.dataset, message=str(e))
                self.logger.exception("Error processing {}", tarball.tarball.name)
                continue
            nsuccess += 1

        return Results(total=ntotal, success=nsuccess)

    def report(self, prog: str, result_string: str):
        """prepare and send report for the unpacked tarballs

        Args:
            prog: name of the running script.
            result_string: composed of the results received after processing of tarballs.
        """
        with tempfile.NamedTemporaryFile(mode="w+t", dir=self.config.TMP) as reportfp:
            reportfp.write(
                f"{prog}.{timestamp()}({self.config.PBENCH_ENV})\n{result_string}\n"
            )
            reportfp.seek(0)

            report = Report(self.config, prog)
            report.init_report_template()
            try:
                report.post_status(timestamp(), "status", reportfp.name)
            except Exception:
                self.logger.exception("{}: failure posting report", prog)
