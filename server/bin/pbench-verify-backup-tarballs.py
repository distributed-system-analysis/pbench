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

import os
import sys
import glob
import hashlib
import shutil
import tempfile
from enum import Enum
from argparse import ArgumentParser
from s3backup import S3Config, Entry

from pbench import PbenchConfig, BadConfig, get_pbench_logger, md5sum
from pbench.report import Report


_NAME_ = "pbench-verify-backup-tarballs"


class Status(Enum):
    SUCCESS = 10
    FAIL = 20


class BackupObject(object):
    def __init__(self, name, dirname):
        self.name = name
        self.dirname = dirname
        self.list_name = "list.{}".format(self.name)
        self.description = self.name


def sanity_check(s3_obj, logger):
    # make sure the S3 bucket exists
    try:
        s3_obj.head_bucket(Bucket=s3_obj.bucket_name)
    except Exception:
        logger.exception(
            "Bucket: {} does not exist or you have no access\n".format(s3_obj.bucket_name))
        s3_obj = None
    return s3_obj


def checkmd5(target_dir, tmpdir, backup_obj, logger):
    # Function to check integrity of results in a local (archive or local
    # backup) directory.
    #
    # This function returns the count of results that failed the MD5 sum
    # check, and raises exceptions on failure.

    tarlist = glob.iglob(os.path.join(target_dir, "*", "*.tar.xz"))
    indicator_file = os.path.join(tmpdir, backup_obj.list_name)
    indicator_file_ok = os.path.join(tmpdir, "{}.ok".
                                     format(backup_obj.list_name))
    indicator_file_fail = os.path.join(tmpdir, "{}.fail".
                                       format(backup_obj.list_name))
    nfailed_md5 = 0
    with open(indicator_file, 'w') as f_list,\
        open(indicator_file_ok, 'w') as f_ok,\
        open(indicator_file_fail, 'w') as f_fail:
        for tar in tarlist:
            result_name = os.path.basename(tar)
            controller = os.path.basename(os.path.dirname(tar))
            md5 = "{}.md5".format(tar)
            f_list.write("{}\n".format(
                os.path.join(controller, result_name)))
            try:
                with open(md5) as f:
                    md5_value = f.readline().split(" ")[0]
            except Exception:
                nfailed_md5 += 1
                logger.exception(
                    "Could not open the MD5 file, {}", md5)
                continue
            md5_returned = md5sum(tar)
            if md5_value == md5_returned:
                f_ok.write("{}: {}\n".format(
                    os.path.join(controller, result_name), "OK"))
            else:
                nfailed_md5 += 1
                f_fail.write("{}: {}\n".format(
                    os.path.join(controller, result_name), "FAILED"))
    return nfailed_md5


def report_failed_md5(backup_obj, tmpdir, report, logger):
    # Function to report the results that failed md5 sum check.
    fail_f = os.path.join(tmpdir, "{}.fail".format(backup_obj.list_name))
    if os.path.exists(fail_f) and os.path.getsize(fail_f) > 0:
        try:
            with open(fail_f) as f:
                failed_list = f.read()
        except Exception:
            # Could not open the file
            logger.exception(
                "Could not open the file {}".format(fail_f))
        else:
            report.write(
                "ERROR: in {}: the calculated MD5 of the following entries "
                "failed to match the stored MD5:\n{}".format(backup_obj.name, failed_list))


def compare_entry_lists(list_one_obj, list_two_obj, list_one, list_two, report):
    # Compare the two lists and report the differences.
    sorted_list_one_content = sorted(list_one, key=lambda k: k.name)
    sorted_list_two_content = sorted(list_two, key=lambda k: k.name)
    len_list_one_content = len(list_one)
    len_list_two_content = len(list_two)
    i, j = 0, 0
    while (i < len_list_one_content) and (j < len_list_two_content):
        if sorted_list_one_content[i] == sorted_list_two_content[j]:
            i += 1
            j += 1
        elif sorted_list_one_content[i].name == sorted_list_two_content[j].name:
            # the md5s are different even though the names are the same
            report_text = "MD5 values don't match for: {}\n".format(
                sorted_list_one_content[i].name)
            report.write(report_text)
            i += 1
            j += 1
        elif sorted_list_one_content[i].name < sorted_list_two_content[j].name:
            report_text = "{}: present in {} but not in {}\n".format(
                                        sorted_list_one_content[i].name,
                                        list_one_obj.description,
                                        list_two_obj.description)
            report.write(report_text)
            i += 1
        else:
            assert sorted_list_one_content[i].name > sorted_list_two_content[j].name, "Logic bomb!"
            report_text = "{}: present in {} but not in {}\n".format(
                                        sorted_list_two_content[j].name,
                                        list_two_obj.description,
                                        list_one_obj.description)
            report.write(report_text)
            j += 1
    assert (i == len_list_one_content) or (j == len_list_two_content), "Logic bomb!"

    if i == len_list_one_content and j < len_list_two_content:
        for entry in sorted_list_two_content[j:len_list_two_content]:
            report_text = "{}: present in {} but not in {}\n".format(
                                                    entry.name,
                                                    list_two_obj.description,
                                                    list_one_obj.description)
            report.write(report_text)
    elif i < len_list_one_content and j == len_list_two_content:
        for entry in sorted_list_one_content[i:len_list_one_content]:
            report_text = "{}: present in {} but not in {}\n".format(
                                                    entry.name,
                                                    list_one_obj.description,
                                                    list_two_obj.description)
            report.write(report_text)
    else:
        assert (i == len_list_one_content) and (j == len_list_two_content), "Logic bomb!"


def entry_list_creation(backup_obj, target_dir, logger):
    # Function to create entry list for results in a local
    # (archive or local backup) directory.
    if not os.path.isdir(target_dir):
        logger.error('Bad {}: {}'.format(backup_obj.name, target_dir))
        return Status.FAIL

    tarlist = glob.iglob(os.path.join(target_dir, "*", "*.tar.xz"))
    content_list = []
    for tar in tarlist:
        result_name = os.path.basename(tar)
        controller = os.path.basename(os.path.dirname(tar))
        md5_file = "{}.md5".format(tar)
        try:
            with open(md5_file) as k:
                md5 = k.readline().split(" ")[0]
        except Exception:
            logger.exception("Could not open the file {}", md5_file)
            continue
        else:
            content_list.append(
                Entry(os.path.join(controller, result_name), md5))
    return content_list


def entry_list_creation_s3(s3_config_obj, logger):
    # Function to create entry list for results in S3.
    if s3_config_obj is None:
        return Status.FAIL

    s3_content_list = []
    kwargs = {'Bucket': s3_config_obj.bucket_name}
    try:
        while True:
            resp = s3_config_obj.list_objects(**kwargs)
            for obj in resp['Contents']:
                md5_returned = obj['ETag'].strip("\"")
                s3_content_list.append(Entry(obj['Key'], md5_returned))
            try:
                kwargs['ContinuationToken'] = resp['NextContinuationToken']
            except KeyError:
                break
    except Exception:
        logger.exception(
            "Something went wrong while listing the objects from S3")
        return Status.FAIL
    else:
        return s3_content_list


def main():
    cfg_name = os.environ.get("CONFIG")
    if not cfg_name:
        print("{}: ERROR: No config file specified; set CONFIG env variable or"
                " use --config <file> on the command line".format(_NAME_),
                file=sys.stderr)
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
            "The setting for ARCHIVE in the config file is {}, but that is not a directory", archive)
        return 1

    # add a BACKUP field to the config object
    config.BACKUP = backup = config.conf.get("pbench-server", "pbench-backup-dir")
    if len(backup) == 0:
        logger.error(
            "Unspecified backup directory, no pbench-backup-dir config in pbench-server section")
        return 1

    if not os.path.isdir(backup):
        logger.error("The setting for BACKUP in the config file is {}, but that is not a directory", backup)
        return 1

    # instantiate the s3config class
    s3_config_obj = S3Config(config, logger)
    s3_config_obj = sanity_check(s3_config_obj, logger)

    logger.info('start-{}', config.TS)

    prog = os.path.basename(sys.argv[0])

    sts = 0
    # N.B. tmpdir is the pathname of the temp directory.
    with tempfile.TemporaryDirectory() as tmpdir:

        archive_obj = BackupObject("ARCHIVE", config.ARCHIVE)
        local_backup_obj = BackupObject("BACKUP", config.BACKUP)
        s3_backup_obj = BackupObject("S3", s3_config_obj)

        # Create entry list for archive
        archive_entry_list = entry_list_creation(archive_obj, config.ARCHIVE, logger)
        if archive_entry_list == Status.FAIL:
            sts += 1

        # Create entry list for backup
        backup_entry_list = entry_list_creation(local_backup_obj, config.BACKUP, logger)
        if backup_entry_list == Status.FAIL:
            sts += 1

        # Create entry list for S3
        s3_entry_list = entry_list_creation_s3(s3_config_obj, logger)
        if s3_entry_list == Status.FAIL:
            sts += 1

        with tempfile.NamedTemporaryFile(mode='w+t', dir=tmpdir) as reportfp:
            reportfp.write("{}.{}({})\n".format(prog, config.TS, config.PBENCH_ENV))

            try:
                # Check the data integrity in ARCHIVE (Question 1).
                md5_result_archive = checkmd5(config.ARCHIVE, tmpdir, archive_obj, logger)
            except Exception:
                msg = "Failed to check data integrity of ARCHIVE ({})".format(config.ARCHIVE)
                logger.exception(msg)
                reportfp.write("{}\n".format(msg))
                sts += 1
            else:
                if md5_result_archive > 0:
                    # Create a report for failed MD5 results from ARCHIVE (Question 1)
                    report_failed_md5(archive_obj, tmpdir, reportfp, logger)
                    sts += 1

            try:
                # Check the data integrity in BACKUP (Question 2).
                md5_result_backup = checkmd5(config.BACKUP, tmpdir, local_backup_obj, logger)
            except Exception:
                msg = "Failed to check data integrity of BACKUP ({})".format(config.BACKUP)
                logger.exception(msg)
                reportfp.write("{}\n".format(msg))
            else:
                if md5_result_backup > 0:
                    # Create a report for failed MD5 results from BACKUP (Question 2)
                    report_failed_md5(local_backup_obj, tmpdir, reportfp, logger)
                    sts += 1

            # Compare ARCHIVE with BACKUP (Questions 3 and 3a).
            compare_entry_lists(archive_obj,
                                local_backup_obj,
                                archive_entry_list,
                                backup_entry_list,
                                reportfp)

            if s3_config_obj is None:
                reportfp.write('S3 backup service is inaccessible.\n')
            else:
                # Compare ARCHIVE with S3 (Questions 4, 4a, and 4b).
                compare_entry_lists(archive_obj,
                                    s3_backup_obj,
                                    archive_entry_list,
                                    s3_entry_list,
                                    reportfp)

            # Rewind to the beginning.
            reportfp.seek(0)

            report = Report(config, _NAME_)
            report.init_report_template()
            try:
                report.post_status(config.timestamp(), "status", reportfp.name)
            except Exception:
                pass

    logger.info('end-{}', config.TS)

    return sts


if __name__ == '__main__':
    status = main()
    sys.exit(status)
