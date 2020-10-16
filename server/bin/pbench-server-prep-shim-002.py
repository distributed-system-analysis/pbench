#!/usr/bin/env python3
# -*- mode: python -*-

# This script is used to prepare the tarballs that a version 002 client
# submits for further processing. It copies the tarballs and their MD5
# sums to the archive (after checking) and sets the state links, so
# that the dispatch script will pick them up and get the ball
# rolling. IOW, it does impedance matching between version 002 clients
# and the server scripts.

import os
import sys
import glob
import shutil
import tempfile

from pathlib import Path

from pbench.common.exceptions import BadConfig
from pbench.common.logger import get_pbench_logger
from pbench.common.utils import md5sum
from pbench.server import PbenchServerConfig
from pbench.server.report import Report
from pbench.server.utils import quarantine


_NAME_ = "pbench-server-prep-shim-002"


class Results(object):
    def __init__(
        self, nstatus="", ntotal=0, ntbs=0, nquarantined=0, ndups=0, nerrs=0,
    ):
        self.nstatus = nstatus
        self.ntotal = ntotal
        self.ntbs = ntbs
        self.nquarantined = nquarantined
        self.ndups = ndups
        self.nerrs = nerrs


def fetch_config_val(config, logger):

    qdir = config.get("pbench-server", "pbench-quarantine-dir")
    if not qdir:
        logger.error("Failed: getconf.py pbench-quarantine-dir pbench-server")
        return None, None

    qdir = Path(qdir).resolve()
    if not qdir.is_dir():
        logger.error("Failed: {} does not exist, or is not a directory", qdir)
        return None, None

    # we are explicitly handling version-002 data in this shim
    receive_dir_prefix = config.get("pbench-server", "pbench-receive-dir-prefix")
    if not receive_dir_prefix:
        logger.error("Failed: getconf.py pbench-receive-dir-prefix pbench-server")
        return None, None

    receive_dir = Path(f"{receive_dir_prefix}-002").resolve()
    if not receive_dir.is_dir():
        logger.error("Failed: {} does not exist, or is not a directory", receive_dir)
        return None, None

    return (qdir, receive_dir)


def qdirs_check(qdir_val, qdir, logger):
    try:
        os.makedirs(qdir)
    except FileExistsError:
        # directory already exists, ignore
        pass
    except Exception:
        logger.exception(
            "os.mkdir: Unable to create {} destination directory: {}", qdir_val, qdir,
        )
        return None
    return qdir


def md5_check(tb, tbmd5, logger):
    # read the md5sum from md5 file
    try:
        with tbmd5.open() as f:
            archive_md5_hex_value = f.readline().split(" ")[0]
    except Exception:
        archive_md5_hex_value = None
        logger.exception("Quarantine: Could not read {}", tbmd5)

    # get hex value of the tarball's md5sum
    try:
        archive_tar_hex_value = md5sum(tb)
    except Exception:
        archive_tar_hex_value = None
        logger.exception("Quarantine: Could not read {}", tb)

    return (archive_md5_hex_value, archive_tar_hex_value)


def process_tb(config, logger, receive_dir, qdir_md5, duplicates, errors):

    # Check for results that are ready for processing: version 002 agents
    # upload the MD5 file as xxx.md5.check and they rename it to xxx.md5
    # after they are done with MD5 checking so that's what we look for.
    list_check = glob.glob(
        os.path.join(receive_dir, "**", "*.tar.xz.md5"), recursive=True
    )

    archive = config.ARCHIVE
    logger.info("{}", config.TS)
    list_check.sort()
    nstatus = ""

    ntotal = ntbs = nerrs = nquarantined = ndups = 0

    for tbmd5 in list_check:
        ntotal += 1

        # full pathname of tarball
        tb = Path(tbmd5[0:-4])
        tbmd5 = Path(tbmd5)

        # directory
        tbdir = tb.parent

        # resultname: get the basename foo.tar.xz and then strip the .tar.xz
        resultname = tb.name

        controller = tbdir.name
        dest = archive / controller

        if all([(dest / resultname).is_file(), (dest / tbmd5.name).is_file()]):
            logger.error("{}: Duplicate: {} duplicate name", config.TS, tb)
            quarantine((duplicates / controller), logger, tb, tbmd5)
            ndups += 1
            continue

        archive_tar_hex_value, archive_md5_hex_value = md5_check(tb, tbmd5, logger)
        if any(
            [
                archive_tar_hex_value != archive_md5_hex_value,
                archive_tar_hex_value is None,
                archive_md5_hex_value is None,
            ]
        ):
            logger.error("{}: Quarantined: {} failed MD5 check", config.TS, tb)
            logger.info("{}: FAILED", tb.name)
            logger.info("md5sum: WARNING: 1 computed checksum did NOT match")
            quarantine((qdir_md5 / controller), logger, tb, tbmd5)
            nquarantined += 1
            continue

        # make the destination directory and its TODO subdir if necessary.
        try:
            os.makedirs(dest / "TODO")
        except FileExistsError:
            # directory already exists, ignore
            pass
        except Exception:
            logger.error("{}: Error in creating TODO directory.", config.TS)
            quarantine(os.path.join(errors, controller), logger, tb, tbmd5)
            nerrs += 1
            continue

        # First, copy the small .md5 file to the destination. That way, if
        # that operation fails it will fail quickly since the file is small.
        try:
            shutil.copy2(tbmd5, dest)
        except Exception:
            logger.error(
                "{}: Error in copying .md5 file to Destination path.", config.TS
            )
            try:
                os.remove(dest / tbmd5.name)
            except FileNotFoundError:
                logger.error(
                    "{}: Warning: cleanup of copy failure failed itself.", config.TS
                )
            quarantine((errors / controller), logger, tb, tbmd5)
            nerrs += 1
            continue

        # Next, mv the "large" tar ball to the destination. If the destination
        # is on the same device, the move should be quick. If the destination is
        # on a different device, the move will be a copy and delete, and will
        # take a bit longer.  If it fails, the file will NOT be at the
        # destination.
        try:
            shutil.move(str(tb), str(dest))
        except Exception:
            logger.error(
                "{}: Error in moving tarball file to Destination path.", config.TS
            )
            try:
                os.remove(dest / resultname)
            except FileNotFoundError:
                logger.error(
                    "{}: Warning: cleanup of copy failure failed itself.", config.TS
                )
            quarantine((errors / controller), logger, tb, tbmd5)
            nerrs += 1
            continue

        # Now that we have successfully moved the tar ball and its .md5 to the
        # destination, we can remove the original .md5 file.
        try:
            os.remove(tbmd5)
        except Exception as exc:
            logger.error(
                "{}: Warning: cleanup of successful copy operation failed: '{}'",
                config.TS,
                exc,
            )

        try:
            os.symlink((dest / resultname), (dest / "TODO" / resultname))
        except Exception as exc:
            logger.error("{}: Error in creation of symlink. '{}'", config.TS, exc)
            # if we fail to make the link, we quarantine the (already moved)
            # tarball and .md5.
            quarantine(
                (errors / controller), logger, (dest / tb), (dest / tbmd5),
            )
            nerrs += 1
            continue

        ntbs += 1

        nstatus = f"{nstatus}{config.TS}: processed {tb}\n"
        logger.info(f"{tb.name}: OK")

    return Results(
        nstatus=nstatus,
        ntotal=ntotal,
        ntbs=ntbs,
        nquarantined=nquarantined,
        ndups=ndups,
        nerrs=nerrs,
    )


def main(cfg_name):
    if not cfg_name:
        print(
            f"{_NAME_}: ERROR: No config file specified; set"
            " _PBENCH_SERVER_CONFIG env variable or use --config <file> on the"
            " command line",
            file=sys.stderr,
        )
        return 2

    try:
        config = PbenchServerConfig(cfg_name)
    except BadConfig as e:
        print(f"{_NAME_}: {e} (config file {cfg_name})", file=sys.stderr)
        return 1

    logger = get_pbench_logger(_NAME_, config)

    qdir, receive_dir = fetch_config_val(config, logger)

    if qdir is None and receive_dir is None:
        return 2

    qdir_md5 = qdirs_check("quarantine", Path(qdir, "md5-002"), logger)
    duplicates = qdirs_check("duplicates", Path(qdir, "duplicates-002"), logger)

    # The following directory holds tarballs that are quarantined because
    # of operational errors on the server. They should be retried after
    # the problem is fixed: basically, move them back into the reception
    # area for 002 agents and wait.
    errors = qdirs_check("errors", Path(qdir, "errors-002"), logger)

    if qdir_md5 is None or duplicates is None or errors is None:
        return 1

    counts = process_tb(config, logger, receive_dir, qdir_md5, duplicates, errors)

    result_string = (
        f"{config.TS}: Processed {counts.ntotal} entries,"
        f" {counts.ntbs} tarballs successful,"
        f" {counts.nquarantined} quarantined tarballs,"
        f" {counts.ndups} duplicately-named tarballs,"
        f" {counts.nerrs} errors."
    )

    logger.info(result_string)

    # prepare and send report
    with tempfile.NamedTemporaryFile(mode="w+t", dir=config.TMP) as reportfp:
        reportfp.write(f"{counts.nstatus}{result_string}\n")
        reportfp.seek(0)

        report = Report(config, _NAME_)
        report.init_report_template()
        try:
            report.post_status(config.timestamp(), "status", reportfp.name)
        except Exception as exc:
            logger.warning("Report post Unsuccesful: '{}'", exc)

    return 0


if __name__ == "__main__":
    cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
    status = main(cfg_name)
    sys.exit(status)
