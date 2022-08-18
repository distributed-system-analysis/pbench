from logging import Logger
import os
from pathlib import Path
import tempfile
from typing import NamedTuple

from pbench.server import PbenchServerConfig
from pbench.server.filetree import FileTree
from pbench.server.report import Report
from pbench.server.utils import get_tarball_md5


class Results(NamedTuple):
    total: int
    success: int


class UnpackTarballs:
    """Unpacks Tarball in the INCOMING Directory"""

    LINKSRC = "TO-UNPACK"

    def __init__(self, config: PbenchServerConfig, logger: Logger):
        """
        Args:
            config: PbenchServerConfig configuration object
            logger: A Pbench python Logger
        """
        self.config = config
        self.logger = logger

    def unpack(self, tb: Path, file_tree: FileTree):
        """Getting md5 value of the tarball and Unpacking Tarball.

        Args:
            tb: Tarball Path
            file_tree: FileTree object
        """
        try:
            tar_md5 = get_tarball_md5(tb)
        except FileNotFoundError as exc:
            self.logger.error(
                "{}: Getting md5 value of tarball '{}' failed: {}",
                self.config.TS,
                tb,
                exc,
            )
            raise

        try:
            file_tree.unpack(tar_md5)
        except Exception as exc:
            self.logger.error(
                "{}: Unpacking of tarball {} failed: {}",
                self.config.TS,
                tb,
                exc,
            )
            raise

    def update_symlink(self, tarball: Path):
        """Creates the symlink in state directories. Removes symlink
        from `TO-UNPACK` state directory after successful unpacking of Tarball.

        Args:
            tarball: Tarball Path
        """
        linkdestlist = self.config.get("pbench-server", "unpacked-states").split(", ")
        controller_name = tarball.parent.parent.name
        dest = self.config.ARCHIVE / controller_name

        for state in linkdestlist:
            try:
                os.symlink(dest / tarball.name, dest / state / tarball.name)
            except Exception as exc:
                self.logger.error(
                    "{}: Error in creation of symlink. {}", self.config.TS, exc
                )
                raise

        try:
            os.unlink(dest / self.LINKSRC / tarball.name)
        except Exception as exc:
            self.logger.error(
                "{}: Error in removing symlink from {} state. {}",
                self.config.TS,
                self.LINKSRC,
                exc,
            )
            raise

    def unpack_tarballs(self, min_size: float, max_size: float) -> Results:
        """Scans for tarballs in the TO-UNPACK subdirectories of the
        ARCHIVE directory and unpacks them using FileTree.unpack() function.

        Args:
            min_size: minimum size of tarball for this Bucket
            max_size: maximum size of tarball for this Bucket

        Returns:
            Results tuple containing the counts of Total and Successful tarballs.
        """
        tarlist = [
            tarball
            for tarball in self.config.ARCHIVE.glob(f"*/{self.LINKSRC}/*.tar.xz")
            if min_size <= Path(tarball).stat().st_size < max_size
        ]

        ntotal = nsuccess = 0
        file_tree = FileTree(self.config, self.logger)

        for tarball in sorted(tarlist):
            ntotal += 1

            try:
                try:
                    tb = Path(tarball).resolve(strict=True)
                except FileNotFoundError as exc:
                    self.logger.error(
                        "{}: Tarball link, '{}', does not resolve to a real location: {}",
                        self.config.TS,
                        tarball,
                        exc,
                    )
                    raise
                self.unpack(tb, file_tree)
                self.update_symlink(tb)
            except Exception:
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
                f"{prog}.{self.config.timestamp()}({self.config.PBENCH_ENV})\n{result_string}\n"
            )
            reportfp.seek(0)

            report = Report(self.config, prog)
            report.init_report_template()
            try:
                report.post_status(self.config.timestamp(), "status", reportfp.name)
            except Exception:
                pass
