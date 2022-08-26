import os
import subprocess

from collections import namedtuple
from logging import Logger
from pathlib import Path

from pbench import PbenchConfig

Results = namedtuple("Results", ["nstatus", "ntotal", "ntbs", "nerr"])


class ProcessTb:
    def __init__(self, config: PbenchConfig, logger: Logger):
        """Processes Tar ball, gets the tar ball from receiving directory
        and copies it to the remote server by creating a subprocess which
        call Agent's 'pbench-results-push' command.

            Args -
                config -- PbenchServer config object
                logger -- logger object to use when emitting log entries during
                            operation

        """
        self.config = config
        self.logger = logger
        self.token = self.config.get("pbench-server", "put-token")
        if not self.token:
            raise ValueError(
                "No value for config option put-token in section pbench-server"
            )
        # receive_dir -- directory where tarballs are received from agent
        self.receive_dir = self._get_receive_dir()

    def _get_receive_dir(self) -> Path:
        receive_dir_prefix = self.config.get(
            "pbench-server", "pbench-receive-dir-prefix"
        )
        if not receive_dir_prefix:
            raise ValueError(
                "Failed: No value for config option pbench-receive-dir-prefix in section pbench-server"
            )

        receive_dir = Path(f"{receive_dir_prefix}-002").resolve()
        if not receive_dir.is_dir():
            raise NotADirectoryError(
                f"Failed: {str(receive_dir)!r} does not exist, or is not a directory",
            )

        return receive_dir

    @staticmethod
    def _results_push(controller: str, tb: Path, token: str):
        """Runs Agent's `pbench-results-push` command with controller, tb
        and token options

        Args -
            controller -- the name of the controller to be associated with the
                          tar ball
            tb -- path of the tar ball
            token -- generated authorised token for Pbench user

        Importance of this function is while running tests we get the
        ability to mock this function and test it easily
        """

        res = subprocess.run(
            ["pbench-results-push", controller, tb, token], capture_output=True
        )
        error = res.stderr
        if res.returncode > 0:
            raise RuntimeError(error)

    def process_tb(self) -> Results:
        """Searches for tarballs in the configured receive directory and
        uploads them to the Pbench server"""

        # Check for results that are ready for processing: version 002 agents
        # upload the MD5 file as xxx.md5.check and they rename it to xxx.md5
        # after they are done with MD5 checking so that's what we look for.
        self.logger.info("{}", self.config.TS)
        nstatus = ""
        ntotal = ntbs = nerr = 0

        for tbmd5 in sorted(self.receive_dir.glob("**/*.tar.xz.md5")):
            ntotal += 1

            # Extracts full pathname of tarball from the name of hashfile
            # by trimming .md5 suffix
            tb = Path(str(tbmd5)[0 : -len(".md5")])
            tbdir = tb.parent
            controller = tbdir.name

            try:
                ProcessTb._results_push(controller, tb, self.token)
            except Exception as e:
                self.logger.error(
                    "{}: Unexpected Error while running Agent's 'pbench-result-push' command: {}",
                    self.config.TS,
                    e,
                )
                nerr += 1
                continue

            try:
                os.remove(tbmd5)
            except Exception as exc:
                self.logger.error(
                    "{}: Cleanup of successful copy operation for MD5 file '{}' failed: '{}'",
                    self.config.TS,
                    tbmd5,
                    exc,
                )
                nerr += 1

            try:
                os.remove(tb)
            except Exception as exc:
                self.logger.error(
                    "{}: Cleanup of successful copy operation for tar ball '{}' failed: '{}'",
                    self.config.TS,
                    tb,
                    exc,
                )
                nerr += 1

            ntbs += 1
            nstatus += f": processed {tb.name}\n"
            self.logger.info(f"{tb.name}: OK")

        return Results(nstatus, ntotal, ntbs, nerr)
