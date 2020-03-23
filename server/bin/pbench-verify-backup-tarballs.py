#!/usr/bin/env python3
# -*- mode: python -*-

"""pbench-verify-backup-tarballs.py

There are three locations for tar balls: the ARCHIVE directory, the BACKUP
directory (an NFS mount typically), and the S3 object store.

The goal is to answer and report on the following questions:

  1. What files in ARCHIVE have bit-rot?

  2. What files in BACKUP have bit-rot?

  3. What files in ARCHIVE are NOT in BACKUP?

     a. And what files in BACKUP are NOT in ARCHIVE?

     NOTE: Ignoring files that have bit-rot, if ARCHIVE and BACKUP have the
     same files, we can be sure their contents are correct because of the
     bit-rot check (the probability of a .md5 file changing it contents at
     the same time that an associated change to its tar ball happens such
     that the MD5 checksum still matches is extremely low, and so not worth
     worrying about for our purposes).

  4. What files in ARCHIVE are NOT in S3?

     a. And what files in S3 are not in ARCHIVE?

     b. And what .md5 file contents in ARCHIVE do NOT match the ETag contents
        in S3?

We only consider comparisons between ARCHIVE and BACKUP, and ARCHIVE and S3,
never between BACKUP and S3. The reason for this is that all differences
found must always result in an action taken to correct the ARCHIVE.  If the
ARCHIVE is missing files, then somebody will have to update the ARCHIVE first,
before updating BACKUP or S3.  And if ARCHIVE has files that are not in BACKUP
or S3, then those files will have been moved backed up first before we can
re-verify.
"""

import errno
import glob
import os
import sys
import tempfile
from enum import Enum

from pbench import PbenchConfig
from pbench.exception import BadConfig
from pbench.logger import get_pbench_logger
from pbench.utils import md5sum
from pbench.report import Report
from pbench.s3backup import Entry, S3Config

_NAME_ = "pbench-verify-backup-tarballs"


class Status(Enum):
    SUCCESS = 10
    FAIL = 20


class BackupObject(object):
    def __init__(self, name, dirname, tmpdir, logger):
        self.name = name
        self.description = self.name
        if dirname is None:
            self.s3_config_obj = None
            self.dirname = None
        elif isinstance(dirname, S3Config):
            self.s3_config_obj = dirname
            self.dirname = None
        else:
            if not os.path.isdir(dirname):
                raise Exception("Bad {}: {}".format(name, dirname))
            self.dirname = dirname
            self.s3_config_obj = None
        self.tmpdir = tmpdir
        self.logger = logger
        self.content_list = None
        self.missing_list = None
        self.error_list = None

    def fs_entry_list_creation(self):
        # Function to create entry list for results in a file-system
        # (archive or backup) directory.
        tarlist = glob.iglob(os.path.join(self.dirname, "*", "*.tar.xz"))
        self.content_list = []
        self.missing_list = []
        self.error_list = []
        for tar in tarlist:
            result_name = os.path.basename(tar)
            controller = os.path.basename(os.path.dirname(tar))
            md5_file = "{}.md5".format(tar)
            try:
                with open(md5_file) as k:
                    md5 = k.readline().split(" ")[0]
            except OSError as ex:
                if ex.errno == errno.ENOENT:
                    self.missing_list.append(tar)
                else:
                    self.error_list.append(tar)
                    self.logger.exception("ERROR reading file {}", md5_file)
                continue
            except Exception:
                self.error_list.append(tar)
                self.logger.exception("ERROR reading file {}", md5_file)
                continue
            else:
                self.content_list.append(
                    Entry(os.path.join(controller, result_name), md5)
                )
        return Status.SUCCESS

    def s3_entry_list_creation(self):
        self.content_list = []
        kwargs = {"Bucket": self.s3_config_obj.bucket_name}
        try:
            # We loop because the objects are returned a "page" at a
            # time and all the pages except the last return a
            # continuation token.
            done = False
            while not done:
                resp = self.s3_config_obj.list_objects(**kwargs)
                for obj in resp["Contents"]:
                    md5_returned = self.s3_config_obj.header_md5(obj)
                    self.content_list.append(Entry(obj["Key"], md5_returned))
                try:
                    kwargs["ContinuationToken"] = resp["NextContinuationToken"]
                except KeyError:
                    # that was the last page
                    done = True
                self.logger.debug(
                    "list_objects: got {} objects{}",
                    len(resp["Contents"]),
                    " - continuing..." if not done else "",
                )

        except Exception:
            self.logger.exception("ERROR fetching list of objects from S3")
            return Status.FAIL
        else:
            return Status.SUCCESS

    def entry_list_creation(self):
        if self.s3_config_obj is not None:
            return self.s3_entry_list_creation()
        elif self.dirname is not None:
            return self.fs_entry_list_creation()
        else:
            return Status.FAIL

    def checkmd5(self):
        # Function to check integrity of results in a local (archive or local
        # backup) directory.
        #
        # This function returns the count of results that failed the MD5 sum
        # check, and raises exceptions on failure.

        self.indicator_file = os.path.join(self.tmpdir, "list.{}".format(self.name))
        self.indicator_file_ok = "{}.ok".format(self.indicator_file)
        self.indicator_file_fail = "{}.fail".format(self.indicator_file)
        self.nfailed_md5 = 0
        with open(self.indicator_file_ok, "w") as f_ok, open(
            self.indicator_file_fail, "w"
        ) as f_fail:
            for tar in self.content_list:
                md5_returned = md5sum(os.path.join(self.dirname, tar.name))
                if tar.md5 == md5_returned:
                    f_ok.write("{}: {}\n".format(tar.name, "OK"))
                else:
                    self.nfailed_md5 += 1
                    f_fail.write("{}: {}\n".format(tar.name, "FAILED"))
        return self.nfailed_md5

    def report_failed_md5(self, report):
        # Function to report the results that failed md5 sum check.
        fail_f = self.indicator_file_fail
        if os.path.exists(fail_f) and os.path.getsize(fail_f) > 0:
            report.write(
                "\nMD5 Errors ({}): the calculated MD5 values of the following entries "
                "failed to match the stored MD5:\n".format(self.name)
            )
            try:
                with open(fail_f) as f:
                    report.write(f.readline())
            except Exception:
                # Could not open/read the file
                msg = "Failure trying to read from the file {}".format(fail_f)
                self.logger.exception(msg)
                report.write("ERROR - {}\n".format(msg))


def compare_entry_lists(list_one_obj, list_two_obj, report, logger):
    # Compare the two lists and report the differences.
    sorted_list_one_content = sorted(list_one_obj.content_list, key=lambda k: k.name)
    sorted_list_two_content = sorted(list_two_obj.content_list, key=lambda k: k.name)
    len_list_one_content = len(sorted_list_one_content)
    len_list_two_content = len(sorted_list_two_content)
    i, j = 0, 0
    while (i < len_list_one_content) and (j < len_list_two_content):
        if sorted_list_one_content[i] == sorted_list_two_content[j]:
            i += 1
            j += 1
        elif sorted_list_one_content[i].name == sorted_list_two_content[j].name:
            # The md5s are different even though the names are the same.
            report_text = "MD5 values don't match for: {}\n".format(
                sorted_list_one_content[i].name
            )
            report.write(report_text)
            logger.debug(report_text)
            i += 1
            j += 1
        elif sorted_list_one_content[i].name < sorted_list_two_content[j].name:
            report_text = "{}: present in {} but not in {}\n".format(
                sorted_list_one_content[i].name,
                list_one_obj.description,
                list_two_obj.description,
            )
            report.write(report_text)
            logger.debug(report_text)
            i += 1
        else:
            assert (
                sorted_list_one_content[i].name > sorted_list_two_content[j].name
            ), "Logic bomb!"
            report_text = "{}: present in {} but not in {}\n".format(
                sorted_list_two_content[j].name,
                list_two_obj.description,
                list_one_obj.description,
            )
            report.write(report_text)
            logger.debug(report_text)
            j += 1
    assert (i == len_list_one_content) or (j == len_list_two_content), "Logic bomb!"

    if i == len_list_one_content and j < len_list_two_content:
        for entry in sorted_list_two_content[j:len_list_two_content]:
            report_text = "{}: present in {} but not in {}\n".format(
                entry.name, list_two_obj.description, list_one_obj.description
            )
            report.write(report_text)
            logger.debug(report_text)
    elif i < len_list_one_content and j == len_list_two_content:
        for entry in sorted_list_one_content[i:len_list_one_content]:
            report_text = "{}: present in {} but not in {}\n".format(
                entry.name, list_one_obj.description, list_two_obj.description
            )
            report.write(report_text)
            logger.debug(report_text)
    else:
        assert (i == len_list_one_content) and (
            j == len_list_two_content
        ), "Logic bomb!"


def sanity_check(s3_obj, logger):
    # make sure the S3 bucket exists
    try:
        s3_obj.head_bucket(Bucket=s3_obj.bucket_name)
    except Exception:
        logger.exception(
            "Bucket: {} does not exist or you have no access\n".format(
                s3_obj.bucket_name
            )
        )
        s3_obj = None
    return s3_obj


def main():
    cfg_name = os.environ.get("_PBENCH_SERVER_CONFIG")
    if not cfg_name:
        print(
            "{}: ERROR: No config file specified; set _PBENCH_SERVER_CONFIG env variable or"
            " use --config <file> on the command line".format(_NAME_),
            file=sys.stderr,
        )
        return 2

    try:
        config = PbenchConfig(cfg_name)
    except BadConfig as e:
        print("{}: {}".format(_NAME_, e), file=sys.stderr)
        return 1

    logger = get_pbench_logger(_NAME_, config)

    archive = config.ARCHIVE
    if not os.path.isdir(archive):
        logger.error(
            "The setting for ARCHIVE in the config file is {}, but that is"
            " not a directory",
            archive,
        )
        return 1

    # add a BACKUP field to the config object
    config.BACKUP = backup = config.conf.get("pbench-server", "pbench-backup-dir")
    if len(backup) == 0:
        logger.error(
            "Unspecified backup directory, no pbench-backup-dir config in"
            " pbench-server section"
        )
        return 1
    if not os.path.isdir(backup):
        logger.error(
            "The setting for BACKUP in the config file is {}, but that is"
            " not a directory",
            backup,
        )
        return 1

    # instantiate the s3config class
    s3_config_obj = S3Config(config, logger)
    s3_config_obj = sanity_check(s3_config_obj, logger)

    logger.info("start-{}", config.TS)
    start = config.timestamp()

    prog = os.path.basename(sys.argv[0])

    sts = 0
    # N.B. tmpdir is the pathname of the temp directory.
    with tempfile.TemporaryDirectory() as tmpdir:

        archive_obj = BackupObject("ARCHIVE", config.ARCHIVE, tmpdir, logger)
        local_backup_obj = BackupObject("BACKUP", config.BACKUP, tmpdir, logger)
        s3_backup_obj = BackupObject("S3", s3_config_obj, tmpdir, logger)

        with tempfile.NamedTemporaryFile(mode="w+t", dir=tmpdir) as reportfp:
            reportfp.write(
                "{}.{} ({}) started at {}\n".format(
                    prog, config.TS, config.PBENCH_ENV, start
                )
            )
            if s3_config_obj is None:
                reportfp.write(
                    "\nNOTICE: S3 backup service is inaccessible; skipping"
                    " ARCHIVE to S3 comparison\n\n"
                )

            # FIXME: Parallelize these three ...

            # Create entry list for archive
            logger.debug("Starting archive list creation")
            ar_start = config.timestamp()
            ret_sts = archive_obj.entry_list_creation()
            if ret_sts == Status.FAIL:
                sts += 1
            logger.debug("Finished archive list ({!r})", ret_sts)

            # Create entry list for backup
            logger.debug("Starting local backup list creation")
            lb_start = config.timestamp()
            ret_sts = local_backup_obj.entry_list_creation()
            if ret_sts == Status.FAIL:
                sts += 1
            logger.debug("Finished local backup list ({!r})", ret_sts)

            # Create entry list for S3
            if s3_config_obj is not None:
                logger.debug("Starting S3 list creation")
                s3_start = config.timestamp()
                ret_sts = s3_backup_obj.entry_list_creation()
                if ret_sts == Status.FAIL:
                    sts += 1
                logger.debug("Finished S3 list ({!r})", ret_sts)

            logger.debug("Checking MD5 signatures of archive")
            ar_md5_start = config.timestamp()
            try:
                # Check the data integrity in ARCHIVE (Question 1).
                md5_result_archive = archive_obj.checkmd5()
            except Exception as ex:
                msg = "Failed to check data integrity of ARCHIVE ({})".format(
                    config.ARCHIVE
                )
                logger.exception(msg)
                reportfp.write("\n{} - '{}'\n".format(msg, ex))
                sts += 1
            else:
                if md5_result_archive > 0:
                    # Create a report for failed MD5 results from ARCHIVE (Question 1)
                    archive_obj.report_failed_md5(reportfp)
                    sts += 1
                    logger.debug(
                        "Checking MD5 signature of archive: {} errors",
                        md5_result_archive,
                    )
            logger.debug("Finished checking MD5 signatures of archive")

            logger.debug("Checking MD5 signatures of local backup")
            lb_md5_start = config.timestamp()
            try:
                # Check the data integrity in BACKUP (Question 2).
                md5_result_backup = local_backup_obj.checkmd5()
            except Exception as ex:
                msg = "Failed to check data integrity of BACKUP ({})".format(
                    config.BACKUP
                )
                logger.exception(msg)
                reportfp.write("\n{} - '{}'\n".format(msg, ex))
            else:
                if md5_result_backup > 0:
                    # Create a report for failed MD5 results from BACKUP (Question 2)
                    local_backup_obj.report_failed_md5(reportfp)
                    sts += 1
                    logger.debug(
                        "Checking MD5 signature of local backup: {} errors",
                        md5_result_backup,
                    )
            logger.debug("Finished checking MD5 signatures of local backup")

            # Compare ARCHIVE with BACKUP (Questions 3 and 3a).
            msg = "Comparing ARCHIVE with BACKUP"
            reportfp.write("\n{}\n{}\n".format(msg, "-" * len(msg)))
            logger.debug("{}: start", msg)
            compare_entry_lists(archive_obj, local_backup_obj, reportfp, logger)
            logger.debug("{}: end", msg)

            if s3_config_obj is not None:
                # Compare ARCHIVE with S3 (Questions 4, 4a, and 4b).
                msg = "Comparing ARCHIVE with S3"
                reportfp.write("\n{}\n{}\n".format(msg, "-" * len(msg)))
                logger.debug("{}: start", msg)
                compare_entry_lists(archive_obj, s3_backup_obj, reportfp, logger)
                logger.debug("{}: end", msg)

            if s3_config_obj is None:
                s3_start = "<skipped>"
            reportfp.write(
                "\n\nPhases (started):\n"
                "Archive List Creation:       {}\n"
                "Local Backup List Creation:  {}\n"
                "S3 List Creation:            {}\n"
                "Archive MD5 Checks:          {}\n"
                "Local Backup MD5 Checks:     {}\n".format(
                    ar_start, lb_start, s3_start, ar_md5_start, lb_md5_start
                )
            )

            end = config.timestamp()
            reportfp.write(
                "\n{}.{} ({}) finished at {}\n".format(
                    prog, config.TS, config.PBENCH_ENV, end
                )
            )

            # Rewind to the beginning.
            reportfp.seek(0)

            logger.debug("Sending report: start")
            report = Report(config, _NAME_)
            report.init_report_template()
            try:
                report.post_status(config.timestamp(), "status", reportfp.name)
            except Exception:
                pass
            logger.debug("Sending report: end")

    logger.info("end-{}", config.TS)

    return sts


if __name__ == "__main__":
    status = main()
    sys.exit(status)
