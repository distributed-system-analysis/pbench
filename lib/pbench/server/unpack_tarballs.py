from dataclasses import dataclass
from pathlib import Path
import tempfile

from pbench.server.cache_manager import CacheManager
from pbench.server.database.models.dataset import Dataset, Metadata
from pbench.server.globals import server
from pbench.server.report import Report
from pbench.server.sync import Operation, Sync


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

    def __init__(self):
        """Construct a Sync and CacheManager object for the unpacking operation."""
        self.sync = Sync(component="unpack")
        self.cache_manager = CacheManager()

    def unpack(self, tb: Target):
        """Encapsulate the call to the CacheManager unpacker.

        Args:
            tb: Identify the Dataset and Tarball
        """

        try:
            self.cache_manager.unpack(tb.dataset.resource_id)
        except Exception as exc:
            server.logger.error(
                "{}: Unpacking of tarball {} failed: {}",
                server.config.TS,
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
        datasets = self.sync.next(Operation.UNPACK)
        tarlist: list[Target] = []
        for d in datasets:
            t = Metadata.getvalue(d, Metadata.TARBALL_PATH)
            if not t:
                server.logger.error(
                    "Dataset {} is missing a value for {}", d, Metadata.TARBALL_PATH
                )
                continue

            try:
                p = Path(t).resolve(strict=True)
                s = p.stat().st_size
            except FileNotFoundError as exc:
                server.logger.error(
                    "{}: Tarball '{}' does not resolve to a file: {}",
                    server.config.TS,
                    t,
                    exc,
                )
                continue
            except Exception:
                server.logger.exception("Unexpected exception on {}", t)
                continue

            if min_size <= s < max_size:
                tarlist.append(Target(dataset=d, tarball=p))

        ntotal = nsuccess = 0

        for tarball in sorted(tarlist, key=lambda e: str(e.tarball)):
            try:
                ntotal += 1
                self.unpack(tarball)
                self.sync.update(
                    dataset=tarball.dataset,
                    did=Operation.UNPACK,
                    enabled=[Operation.INDEX],
                )
            except Exception:
                server.logger.exception("Error processing {}", tarball.tarball.name)
                continue
            nsuccess += 1

        return Results(total=ntotal, success=nsuccess)

    def report(self, prog: str, result_string: str):
        """prepare and send report for the unpacked tarballs

        Args:
            prog: name of the running script.
            result_string: composed of the results received after processing of tarballs.
        """
        with tempfile.NamedTemporaryFile(mode="w+t", dir=server.config.TMP) as reportfp:
            reportfp.write(
                f"{prog}.{server.config.timestamp()}({server.config.PBENCH_ENV})\n{result_string}\n"
            )
            reportfp.seek(0)

            report = Report(prog)
            report.init_report_template()
            try:
                report.post_status(server.config.timestamp(), "status", reportfp.name)
            except Exception:
                server.logger.exception("{}: failure posting report", prog)
