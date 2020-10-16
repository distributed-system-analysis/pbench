#!/usr/bin/env python3
# -*- mode: python -*-

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
from pbench.server.s3backup import S3Config, Status, NoSuchKey
from pbench.server.utils import rename_tb_link, quarantine


_NAME_ = "pbench-backup-tarballs"

# The link source and destination for this operation of this script.
_linksrc = "TO-BACKUP"
_linkdestfail = "BACKUP-FAILED"
_linkdest = "BACKED-UP"


class LocalBackupObject:
    def __init__(self, config):
        self.backup_dir = config.BACKUP
        self.qdir = config.QDIR


class Results:
    def __init__(
        self,
        ntotal=0,
        nbackup_success=0,
        nbackup_fail=0,
        ns3_success=0,
        ns3_fail=0,
        nquaran=0,
    ):
        self.ntotal = ntotal
        self.nbackup_success = nbackup_success
        self.nbackup_fail = nbackup_fail
        self.ns3_success = ns3_success
        self.ns3_fail = ns3_fail
        self.nquaran = nquaran


def sanity_check(lb_obj, s3_obj, config, logger):
    # make sure the local backup directory is present
    backup = config.BACKUP

    if not backup:
        logger.error(
            "Unspecified backup directory, no pbench-backup-dir config in pbench-server section"
        )
        lb_obj = None
    else:
        try:
            os.mkdir(backup)
        except FileExistsError:
            # directory already exists, verify it
            backuppath = config.get_valid_dir_option("BACKUP", backup, logger)
            if not backuppath:
                lb_obj = None
        except Exception as exc:
            logger.error(
                "os.mkdir: Unable to create backup destination directory: {} '{}'",
                backup,
                exc,
            )
            lb_obj = None

    # make sure the quarantine directory is present
    qdir = config.QDIR

    if not qdir:
        logger.error(
            "Unspecified quarantine directory, no pbench-quarantine-dir config in pbench-server section"
        )
        lb_obj = None
    else:
        qdirpath = config.get_valid_dir_option("QUARANTINE", qdir, logger)
        if not qdirpath:
            lb_obj = None

    # make sure the S3 bucket is defined, exists and is accessible
    if s3_obj.bucket_name is None:
        logger.warning("Bucket not defined in config file - S3 backup is disabled.")
        s3_obj = None
    else:
        try:
            s3_obj.head_bucket(s3_obj.bucket_name)
        except Exception:
            logger.warning(
                "Bucket {} does not exist or is not accessible - S3 backup is disabled",
                s3_obj.bucket_name,
            )
            s3_obj = None

    return (lb_obj, s3_obj)


def backup_to_local(
    lb_obj,
    logger,
    controller_path,
    controller,
    tb,
    tar,
    resultname,
    archive_md5,
    archive_md5_hex_value,
):
    logger.debug("Start local backup of {}.", tar)
    if lb_obj is None:
        # Short-circuit operation when we don't have an lb object. This can
        # happen when the expected result of sanity check does not exist, or
        # for other errors where we still want to backup in S3.
        return Status.FAIL

    backup_controller_path = Path(lb_obj.backup_dir, controller)

    # make sure the controller is present in local backup directory
    backup_controller_path.mkdir(exist_ok=True)

    if not backup_controller_path.exists():
        logger.error(
            "os.mkdir: Unable to create backup destination directory: {}",
            backup_controller_path,
        )
        return Status.FAIL

    # Check if tarball exists in local backup
    backup_tar = backup_controller_path / resultname
    if backup_tar.exists() and backup_tar.is_file():
        backup_md5 = backup_controller_path / f"{resultname}.md5"

        # check that the md5 file exists and it is a regular file
        if backup_md5.exists() and backup_md5.is_file():
            pass
        else:
            # backup md5 file does not exist or it is not a regular file
            logger.error("{} does not exist or it is not a regular file", backup_md5)
            return Status.FAIL

        # read backup md5 file
        try:
            with backup_md5.open() as f:
                backup_md5_hex_value = f.readline().split(" ")[0]
        except Exception:
            # Could not read file
            logger.exception("Could not read file {}", backup_md5)
            return Status.FAIL
        else:
            if archive_md5_hex_value == backup_md5_hex_value:
                # declare success
                logger.info("Already locally backed-up: {}/{}", controller, resultname)
                return Status.SUCCESS
            else:
                # md5 file of archive and backup does not match
                logger.error(
                    "{}/{} already exists in backup but md5 sums of archive and backup disagree",
                    controller,
                    resultname,
                )
                return Status.FAIL
    else:
        tar_done = False

        # copy the md5 file from archive to backup
        try:
            shutil.copy(archive_md5, backup_controller_path)
        except Exception:
            # couldn't copy md5 file
            md5_done = False
            logger.exception(
                "shutil.copy: Unable to copy {} from archive to backup: {}",
                archive_md5,
                backup_controller_path,
            )
        else:
            md5_done = True

        # copy the tarball from archive to backup
        if md5_done:
            try:
                shutil.copy(tar, backup_controller_path)
            except Exception:
                # couldn't copy tarball
                tar_done = False
                logger.exception(
                    "shutil.copy: Unable to copy {} from archive to backup: {}",
                    tar,
                    backup_controller_path,
                )

                # remove the copied md5 file from backup
                bmd5_file = backup_controller_path / f"{resultname}.md5"
                if bmd5_file.exists():
                    try:
                        bmd5_file.remove(bmd5_file)
                    except Exception:
                        logger.exception("Unable to remove: {}", bmd5_file)
            else:
                tar_done = True

        logger.debug("End local backup of {}.", tar)
        if md5_done and tar_done:
            logger.info("Local backup of {}/{} successful", controller, resultname)
            return Status.SUCCESS
        else:
            return Status.FAIL


def backup_to_s3(
    s3_obj,
    logger,
    controller_path,
    controller,
    tb,
    tar,
    resultname,
    archive_md5_hex_value,
):
    if s3_obj is None:
        # Short-circuit operation when we don't have an S3 object to work with
        # when executing.  This can happen when the expected bucket does not
        # exist, or for other errors where we still want to backup locally.
        return Status.FAIL

    logger.debug("Start S3 backup of {}.", tar)
    s3_resultname = os.path.join(controller, resultname)

    # Check if the result already present in s3 or not
    try:
        tbh = s3_obj.get_tarball_header(Bucket=s3_obj.bucket_name, Key=s3_resultname)
    except NoSuchKey:
        s3_md5 = None
    except Exception as e:
        logger.error("Exception raised by get_tarball_header(): {}", e)
        return Status.FAIL
    else:
        s3_md5 = s3_obj.s3_md5(tbh)

    if s3_md5 is not None:
        # compare md5 which we already have so no need to recalculate
        if archive_md5_hex_value == s3_md5:
            # declare success
            logger.info(
                "The tarball {} is already present in S3 bucket with same md5",
                s3_resultname,
            )
            _status = Status.SUCCESS
        else:
            logger.error(
                "The tarball {} is already present in S3 bucket, but with different MD5",
                s3_resultname,
            )
            _status = Status.FAIL
        return _status

    size = s3_obj.getsize(str(tar))
    logger.debug("tarball: {}, size = {}", tar, size)
    with open(tar, "rb") as f:
        sts = s3_obj.put_tarball(
            Name=tar,
            Body=f,
            Size=size,
            ContentMD5=archive_md5_hex_value,
            Bucket=s3_obj.bucket_name,
            Key=s3_resultname,
        )
    logger.debug("End S3 backup of {}.", tar)

    return sts


def backup_data(lb_obj, s3_obj, config, logger):
    qdir = config.QDIR

    tarlist = glob.iglob(os.path.join(config.ARCHIVE, "*", _linksrc, "*.tar.xz"))
    ntotal = nbackup_success = nbackup_fail = ns3_success = ns3_fail = nquaran = 0

    for tb in sorted(tarlist):
        ntotal += 1
        # resolve the link
        try:
            tar = Path(tb).resolve(strict=True)
        except FileNotFoundError:
            logger.error("Tarball link, '{}', does not resolve to a real location", tb)

        logger.debug("Start backup of {}.", tar)
        # check tarball exist and it is a regular file
        if tar.exists() and tar.is_file():
            pass
        else:
            # tarball does not exist or it is not a regular file
            quarantine(qdir, logger, tb)
            nquaran += 1
            logger.error(
                "Quarantine: {}, {} does not exist or it is not a regular file",
                tb,
                tar,
            )
            continue

        archive_md5 = Path(f"{tar}.md5")
        # check that the md5 file exists and it is a regular file
        if archive_md5.exists() and archive_md5.is_file():
            pass
        else:
            # md5 file does not exist or it is not a regular file
            quarantine(qdir, logger, tb)
            nquaran += 1
            logger.error(
                "Quarantine: {}, {} does not exist or it is not a regular file",
                tb,
                archive_md5,
            )
            continue

        # read the md5sum from md5 file
        try:
            with archive_md5.open() as f:
                archive_md5_hex_value = f.readline().split(" ")[0]
        except Exception:
            # Could not read file.
            quarantine(qdir, logger, tb)
            nquaran += 1
            logger.exception("Quarantine: {}, Could not read {}", tb, archive_md5)
            continue

        # match md5sum of the tarball to its md5 file
        try:
            archive_tar_hex_value = md5sum(tar)
        except Exception:
            # Could not read file.
            quarantine(qdir, logger, tb)
            nquaran += 1
            logger.exception("Quarantine: {}, Could not read {}", tb, tar)
            continue

        if archive_tar_hex_value != archive_md5_hex_value:
            quarantine(qdir, logger, tb)
            nquaran += 1
            logger.error(
                "Quarantine: {}, md5sum of {} does not match with its md5 file {}",
                tb,
                tar,
                archive_md5,
            )
            continue

        resultname = tar.name
        controller_path = tar.parent
        controller = controller_path.name

        # This will handle all the local backup related
        # operations and count the number of successes and failures.
        local_backup_result = backup_to_local(
            lb_obj,
            logger,
            controller_path,
            controller,
            tb,
            tar,
            resultname,
            archive_md5,
            archive_md5_hex_value,
        )

        if local_backup_result == Status.SUCCESS:
            nbackup_success += 1
        elif local_backup_result == Status.FAIL:
            nbackup_fail += 1
        else:
            assert (
                False
            ), f"Impossible situation, local_backup_result = {local_backup_result!r}"

        # This will handle all the S3 bucket related operations
        # and count the number of successes and failures.
        s3_backup_result = backup_to_s3(
            s3_obj,
            logger,
            controller_path,
            controller,
            tb,
            tar,
            resultname,
            archive_md5_hex_value,
        )

        if s3_backup_result == Status.SUCCESS:
            ns3_success += 1
        elif s3_backup_result == Status.FAIL:
            ns3_fail += 1
        else:
            assert (
                False
            ), f"Impossible situation, s3_backup_result = {s3_backup_result!r}"

        if local_backup_result == Status.SUCCESS and (
            s3_obj is None or s3_backup_result == Status.SUCCESS
        ):
            # Move tar ball symlink to its final resting place
            rename_tb_link(tb, Path(controller_path, _linkdest), logger)
        else:
            # Do nothing when the backup fails, allowing us to retry on a
            # future pass.
            pass
        logger.debug("End backup of {}.", tar)

    return Results(
        ntotal=ntotal,
        nbackup_success=nbackup_success,
        nbackup_fail=nbackup_fail,
        ns3_success=ns3_success,
        ns3_fail=ns3_fail,
        nquaran=nquaran,
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
        print(f"{_NAME_}: {e}", file=sys.stderr)
        return 1

    logger = get_pbench_logger(_NAME_, config)

    # Add a BACKUP and QDIR field to the config object
    config.BACKUP = config.conf.get("pbench-server", "pbench-backup-dir")
    config.QDIR = config.get("pbench-server", "pbench-quarantine-dir")

    # call the LocalBackupObject class
    lb_obj = LocalBackupObject(config)

    # call the S3Config class
    s3_obj = S3Config(config, logger)

    lb_obj, s3_obj = sanity_check(lb_obj, s3_obj, config, logger)

    if lb_obj is None and s3_obj is None:
        return 3

    logger.info("start-{}", config.TS)

    # Initiate the backup
    counts = backup_data(lb_obj, s3_obj, config, logger)

    result_string = (
        f"Total processed: {counts.ntotal},"
        f" Local backup successes: {counts.nbackup_success},"
        f" Local backup failures: {counts.nbackup_fail},"
        f" S3 upload successes: {counts.ns3_success},"
        f" S3 upload failures: {counts.ns3_fail},"
        f" Quarantined: {counts.nquaran}"
    )

    logger.info(result_string)

    prog = Path(sys.argv[0]).name

    # prepare and send report
    with tempfile.NamedTemporaryFile(mode="w+t", dir=config.TMP) as reportfp:
        reportfp.write(
            f"{prog}.{config.timestamp()}({config.PBENCH_ENV})\n{result_string}\n"
        )
        reportfp.seek(0)

        report = Report(config, _NAME_)
        report.init_report_template()
        try:
            report.post_status(config.timestamp(), "status", reportfp.name)
        except Exception:
            pass

    logger.info("end-{}", config.TS)

    return 0


if __name__ == "__main__":
    cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
    status = main(cfg_name)
    sys.exit(status)
