import shutil
import subprocess
from collections import namedtuple
from logging import Logger
from pathlib import Path

from pbench import PbenchConfig, md5sum

Results = namedtuple(
    "Results",
    ["nstatus", "ntotal", "ntbs", "ndups", "nqua", "nerr", "nserr", "ncerr", "nlerr"],
)


class ProcessTb:
    def __init__(self, config: PbenchConfig, logger: Logger):
        """Processes Tar ball, gets the tar ball from receiving directory
        and copies it to the remote server by creating a subprocess which
        call agent's 'pbench-results-push' command.

        Args:
            config : PbenchServer config object
            logger : logger object to use when emitting log entries during
                operation

        Raises:
            ValueError when the pbench-receive-dir-prefix is not provided, or
                when both a token and a set of dispatch-states are not provided
            NotADirectoryError when the reception directory does not exist
        """
        self.config = config
        self.logger = logger
        # The new pbench server PUT API token to use when copying tar balls to
        # the remote server.
        self.token = self.config.get("pbench-server", "put-token")
        # Perform local directory-based dispatching for additional operations
        # (e.g. unpacking tar balls, backups, etc.).
        dispatch_states_str = self.config.get("pbench-server", "dispatch-states")
        if not self.token and not dispatch_states_str:
            raise ValueError(
                "The 'pbench-server' section must either provide a value for"
                " the 'put-token' option, and/or the 'dispatch-states' option"
            )
        self.dispatch_states = (
            [] if not dispatch_states_str else dispatch_states_str.split(" ")
        )
        # Directory where tarballs are received from an agent SSH operation
        self.receive_dir = self._get_receive_dir()
        self.archive = Path(self.config.ARCHIVE)
        self.q_dir = Path(self.config.get("pbench-server", "pbench-quarantine-dir"))
        self.q_dir.mkdir(exist_ok=True)
        self.q_md5 = self.q_dir / f"md5-{self.version}"
        self.q_md5.mkdir(exist_ok=True)
        self.q_dups = self.q_dir / f"duplicates-{self.version}"
        self.q_dups.mkdir(exist_ok=True)

    def _get_receive_dir(self) -> Path:
        self.version = self.config.get(
            "pbench-server", "pbench-move-results-receive-versions"
        )
        receive_dir_prefix = self.config.get(
            "pbench-server", "pbench-receive-dir-prefix"
        )
        if not receive_dir_prefix:
            raise ValueError(
                "Failed: No value for config option pbench-receive-dir-prefix"
                " in section pbench-server"
            )

        receive_dir = Path(f"{receive_dir_prefix}-{self.version}").resolve()
        if not receive_dir.is_dir():
            raise NotADirectoryError(
                f"Failed: {str(receive_dir)!r} does not exist, or is not a directory",
            )

        return receive_dir

    @staticmethod
    def _results_push(tb: Path, token: str, satellite: str):
        """Runs agent's `pbench-results-push` command to push a tar ball using
        the given token with optional satellite metdata

        Importance of this function is while running tests we get the ability to
        mock this function and test it easily.

        Args:
            tb : path of the tar ball
            token : generated authorised token for Pbench user
            satellite : (optional) prefix of the pbench's satellite server

        Raises:
            RuntimeError when a non-zero exit code is returned by the push op
        """
        results_push = f"pbench-results-push {tb} --token={token}"

        if satellite:
            results_push += f" --metadata=server.origin:{satellite}"

        res = subprocess.run(
            [
                "bash",
                "-l",
                "-c",
                results_push,
            ],
            capture_output=True,
        )
        error = res.stderr

        if res.returncode > 0:
            raise RuntimeError(error)

    def remove(self, tgt: Path, ctx: str) -> int:
        """Convenience method to encapsulate remove of a target file and error
        handling

        Args:
            tgt : target Path object to remove
            ctx : context string to include in the error message

        Returns:
            0 on success, 1 on error
        """
        try:
            tgt.unlink()
        except Exception as exc:
            self.logger.error(
                "{}: in {}, removal of file '{}' failed: '{}'",
                self.config.TS,
                ctx,
                tgt,
                exc,
            )
            ret_val = 1
        else:
            ret_val = 0
        return ret_val

    def quarantine(self, qdir: Path, tb: Path):
        """Quarantine a tar ball and its .md5 file

        Args:
            qdir : the quarantine sub-directory to place tar ball into
            tb : the tar ball Path object to be quarantined
        """
        try:
            qdir.mkdir(exist_ok=True)
        except Exception:
            self.logger.exception(
                "While quarantining '{}', failed to create quarantine directory '{}'",
                tb,
                qdir,
            )
            return
        try:
            shutil.move(tb, qdir)
        except Exception:
            self.logger.exception(
                "While quarantining '{}', failed to move tar ball into directory '{}'",
                tb,
                qdir,
            )
        tb_md5 = tb.parent / f"{tb.name}.md5"
        try:
            shutil.move(tb_md5, qdir)
        except Exception:
            self.logger.exception(
                "While quarantining '{}', failed to move tar ball .md5 into directory '{}'",
                tb,
                qdir,
            )

    def create_state_dirs(self, dest: Path):
        """Create all the state directories.

        Args:
            dest : destination controller directory in the archive tree
        """
        dest.mkdir(exist_ok=True)
        for state_d in self.config.LINKDIRS.split(" "):
            (dest / state_d).mkdir(exist_ok=True)

    def verify_md5sum(self, tb: Path, tbmd5: Path):
        """Verify the MD5 check-sum for the given tar ball is valid.

        Raises:
            RuntimeError when the check-sum is not valid
        """
        md5val_f = tbmd5.read_text().split(" ")[0]
        md5val_c = md5sum(str(tb))
        if md5val_f != md5val_c:
            raise RuntimeError(
                "Calculated MD5 value for tar ball '{tb}', '{md5val_c}', does not match its .md5 file, '{md5val_f}'"
            )

    def move_to_archive(self, tb: Path, tbmd5: Path, dest: Path):
        """Move the given tar ball and .md5 file to the given archive tree
        destination controller directory

        Raises:
            RuntimeError when any step of the process encounters an error,
            cleaning up the destination directory
        """
        # Copy tar ball .md5 to archive tree
        shutil.copy(tbmd5, dest)
        # Move tar ball to archive tree
        try:
            shutil.move(tb, dest)
        except Exception:
            (dest / tbmd5.name).unlink()
            raise
        # Restorecon in the archive tree
        restorecon_cmd = [
            "bash",
            "-l",
            "-c",
            f"restorecon {dest}/{tb.name} {dest}/{tbmd5.name}",
        ]
        try:
            subprocess.run(restorecon_cmd, check=True, capture_output=True)
        except Exception:
            (dest / tb.name).unlink()
            (dest / tbmd5.name).unlink()
            raise
        # Remove reception area .md5 file
        self.remove(tbmd5, "cleanup of successful copy")

    def create_dest_symlinks(self, tb: Path, dest: Path) -> int:
        """Create destination symlinks for state directories.

        The `TODO` state is skipped entirely, and the list of dispatch states
        are used directly.

        Returns:
            0 on success, a count of errors on failure
        """
        target = dest / tb.name
        if not target.is_file():
            self.logger.error(
                "{}: INTERNAL ERROR - destination tar ball '{}' does not exist",
                self.config.TS,
                target,
            )
            return 1
        nerr = 0
        for state_d_str in self.dispatch_states:
            state_d = dest / state_d_str
            state_d_tb = state_d / tb.name
            try:
                state_d_tb.symlink_to(target)
            except Exception as exc:
                self.logger.error(
                    "{}: Cannot create '{}' link to '{}': '{}'",
                    self.config.TS,
                    state_d_tb,
                    target,
                    exc,
                )
                nerr += 1
        return nerr

    def process_tb(self) -> Results:
        """Searches for tarballs in the configured receive directory and uploads
        them to the Pbench server

        Returns:
            a Results named tuple
        """

        # Check for results that are ready for processing: version 002 agents
        # upload the MD5 file as xxx.md5.check and they rename it to xxx.md5
        # after they are done with MD5 checking so that's what we look for.
        self.logger.info("{}", self.config.TS)
        nstatus = ""
        ntotal = ntbs = ndups = nqua = nerr = nserr = ncerr = nlerr = 0
        for tbmd5 in sorted(self.receive_dir.glob("**/*.tar.xz.md5")):
            ntotal += 1

            # Old prep-shim did (quarantining any failed step)
            # 1. check if archive tree already has the tar ball or .md5 in it
            #    and quarantine if so
            # 2. create the TODO sub-directory
            # 3. Copy the tar ball .md5 file to the archive tree
            # 4. Move the tar ball file to the archive tree
            # 5. restorecon in the archive tree destination
            # 6. remove the reception area .md5 file
            # 7. create a symlink for the tar ball in the TODO directory

            # Old dispatch did (quarantining "DUPLICATE__NAME" tar balls, etc.)
            # 1. Creates all the state directories
            # 2. Verifies the tar ball's MD5 signature
            # 3. Creates all the link destination directory symlinks

            # Combined operations will do
            # 1. PUT API if have a token
            # 2. p1
            # 3. d1
            # 4. p3
            # 5. d2
            # 6. p4
            # 7. p5
            # 8. p6
            # 9. d3

            # Extracts full path name of tar ball from the name of the .md5 file
            # by trimming off the suffix.
            tb = Path(str(tbmd5)[0 : -len(".md5")])
            controller = tb.parent.name
            satellite_prefix = None
            if "::" in controller:
                satellite_prefix, controller = controller.split("::")

            if self.token:
                # Step 1
                # Only attempt to push a tar ball to a new Pbench Server via its
                # PUT API when we have a token to use.  Any exceptions
                # encountered are ignored s
                try:
                    ProcessTb._results_push(tb, self.token, satellite_prefix)
                except Exception as e:
                    log_meth = (
                        self.logger.warning
                        if self.dispatch_states
                        else self.logger.error
                    )
                    log_meth(
                        "{}: Unexpected error while running agent's 'pbench-result-push' command: {}",
                        self.config.TS,
                        e,
                    )
                    if not self.dispatch_states:
                        # We have been asked to do one job, failures are errors
                        # and we don't remove the failing tar ball so that the
                        # PUT API can be retried.
                        nerr += 1
                        continue

            if not self.dispatch_states:
                # We only have PUT API tasks cleanup the tar ball we just PUT.
                ncerr += self.remove(tbmd5, "cleanup of successful PUT API operation")
                ncerr += self.remove(tb, "cleanup of successful PUT API operation")
            else:
                # Step 2
                # We have dispatch states configured, check to see if this tar
                # ball is already in the archive tree.
                dest = self.archive / controller
                dest_tb = dest / tb.name
                dest_tbmd5 = dest / tbmd5.name
                if dest_tb.exists() or dest_tbmd5.exists():
                    self.quarantine(self.q_dups / controller, tb)
                    self.logger.error(
                        "{}: Duplicate: '{}' duplicate name", self.config.TS, tb
                    )
                    ndups += 1
                    continue

                # Step 3
                # Verify .MD5
                try:
                    self.verify_md5sum(tb, tbmd5)
                except Exception as exc:
                    self.quarantine(self.q_md5 / controller, tb)
                    self.logger.error(
                        "{}: Quarantined: '{}' failed MD5 check: '{}'",
                        self.config.TS,
                        tb,
                        exc,
                    )
                    nqua += 1
                    continue

                # Step 4
                # Create state directories
                try:
                    self.create_state_dirs(dest)
                except Exception as exc:
                    self.logger.error(
                        "{}: Creation of controller '{}' processing directories failed for '{}': '{}'",
                        self.config.TS,
                        controller,
                        tb.name,
                        exc,
                    )
                    nserr += 1
                    continue

                # Steps 5, 6, 7, & 8
                # Copy tar ball .md5 to archive tree
                # Move tar ball to archive tree
                # Restorecon in the archive tree
                # Remove reception area .md5 file
                try:
                    self.move_to_archive(tb, tbmd5, dest)
                except Exception as exc:
                    self.logger.error(
                        "{}: move to archive for tar ball '{}' failed: '{}'",
                        self.config.TS,
                        tb,
                        exc,
                    )
                    nerr += 1
                    continue

                # Step 9
                # Create all the link destination directory symlinks
                try:
                    self.create_dest_symlinks(tb, dest)
                except Exception:
                    nlerr += 1

            ntbs += 1
            nstatus += f": processed {tb.name}\n"
            self.logger.info(f"{tb.name}: OK")

        return Results(nstatus, ntotal, ntbs, ndups, nqua, nerr, nserr, ncerr, nlerr)
