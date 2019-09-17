#!/usr/bin/env python3
# -*- mode: python -*-


""" 
# When tarballs are copied to archive area by shim. Then pbench dispatch 
# set state to know what processing needs to be done to each tarball. it is done by 
# setting symlinks in designated directories

# those directories are scanned by corresponding scripts

# the work that pbench-dispatch is left for is only to move symlinks from TODO to 
# TO-UNPACK and TO-BACKUP

# then pbench-unpack-tarball will shift to UNPACKED, TO_INDEX, and any other
# pbench-unpack script can set the state for first the state which need tarballs itself
# and then set the state for the one which need unpacked tarballs 
"""

import os
import sys
import glob
import hashlib
import shutil
import tempfile
import tarfile
import re
from contextlib import closing
from time import time
from enum import Enum
from argparse import ArgumentParser
from s3backup import S3Config, Entry

from pbench import PbenchConfig, BadConfig, get_pbench_logger, md5sum, quarantine
from pbench.report import Report

_NAME_ = "pbench-dispatch-unpack-tarballs"

class Results(object):
    def __init__(self, ntotal=0, ntb=0, nerrs=0,
                 ndups=0, ninfo=0):
        self.ntotal = ntotal
        self.ntb = ntb
        self.nerrs = nerrs
        self.ndups = ndups
        self.ninfo = ninfo

def copy_symlinks(state_list, linkdestlist, controller_path, link):

    link_basename = os.path.basename(link)

    totsuc=toterr=0

    for state in linkdestlist:
        pathh = os.path.join(controller_path,state,"")
        os.makedirs(pathh, exist_ok=True)
        os.symlink(link, os.path.join(pathh,link_basename))      
        if os.path.islink(os.path.join(pathh,link_basename)):
            totsuc = totsuc + 1
        else:
            logger.info("Cannot create {} link to {}".format(link, state))
            toterr = toterr + 1

    state_list.extend([totsuc, toterr])

    return state_list

def check_md5(config, archive_md5, logger, tb, link):

    qdir = config.QDIR

    # check md5 file exist and it is a regular file
    if os.path.exists(archive_md5) and os.path.isfile(archive_md5):
        pass
    else:
        # md5 file does not exist or it is not a regular file
        quarantine(qdir, logger, tb)
        logger.error(
            "Quarantine: {}, {} does not exist or it is not a regular file".format(tb, archive_md5))
        return 0

    # read the md5sum from md5 file
    try:
        with open(archive_md5) as f:
            archive_md5_hex_value = f.readline().split(" ")[0]
    except Exception:
        # Could not read file.
        quarantine(qdir, logger, tb)
        logger.exception(
            "Quarantine: {}, Could not read {}".format(tb, archive_md5))
        return 0

    # match md5sum of the tb to its md5 file
    try:
        archive_tar_hex_value = md5sum(link)
    except Exception:
        # Could not read file.
        quarantine(qdir, logger, tb)
        logger.exception(
            "Quarantine: {}, Could not read {}".format(tb, link))
        return 0
    
    if archive_tar_hex_value != archive_md5_hex_value:
        return 1

def dispatch_unpack(config, linkdestlist, unpack_linkdestlist, logger):

    archive = config.ARCHIVE
    qdir = config.QDIR
    incoming = config.INCOMING
    linksrc = "TODO"
    linkdest = "UNPACKED"

    tblist = glob.iglob(os.path.join(archive,'*',linksrc, '*.tar.xz'))

    ntotal=ntb=nerrs=ndups=ninfo=0

    for tb in tblist:

        ntotal=ntotal+1
        link = os.path.realpath(tb)
        archive_md5 = ("{}.md5".format(link))

        md5_res = check_md5(config, archive_md5, logger, tb, link)

        if md5_res == 0:
            continue

        linksrc_path = os.path.dirname(tb) 
        tb_linksrc = os.path.basename(linksrc_path)
        
        controller_path = os.path.dirname(linksrc_path)
        controller = os.path.basename(controller_path)
        controller_dir = os.path.dirname(controller_path)

        resultname = os.path.basename(tb)
        resultname = resultname[:-7]

        if (linksrc != tb_linksrc):
            # All is NOT well: we expect $linksrc as the parent directory name
            # of the symlink tb name.
            logger.error("Fatal - unexpected linksrc for tb")

        if( archive != controller_dir):
            # The controller's parent is not $ARCHIVE!
            logger.error("FATAL - unexpected archive directory for tb")

        if(len(link) == 0):
            logger.info("Symlink target for tb does not exist")
            nerrs = nerrs+1
            quarantine(qdir, logger, tb)
            continue

        if(resultname[:15] == ("DUPLICATE__NAME")):
            ndups = ndups +1
            quarantine(qdir, logger, tb)
            if os.path.isfile(tb):
                logger.info("Cannot remove tarball links")
            continue

        if md5_res == 1:
            nerrs=nerrs+1
            quarantine(qdir, logger, tb)
            logger.error(
                "Quarantine: {}, md5sum of {} does not match with its md5 file {}".format(tb, link, archive_md5))
            if os.path.isfile(tb):
                logger.info("Cannot remove tarball links")
            continue

        income = incoming

        income=os.path.join(income,controller,resultname)
        os.makedirs(income)
        if not os.path.exists(income):
            nerrs=nerrs+1
            continue

        income_unpack = income+".unpack"
        os.makedirs(income_unpack)
        if not os.path.exists(income_unpack):
            logger.info("'mkdir {}.unpack' failed for {}".format(resultname, tb))
            nerrs=nerrs+1
            continue

        income_unpack = os.path.join(income_unpack,"")

        start_time=time()
        if (tb.endswith("tar.xz")):
            if os.path.exists(os.path.realpath(tb)):
                tar = tarfile.open(name=os.path.realpath(tb), mode="r")
                tar.extractall(path=income_unpack)
                tar.close()
        else:
            logger.info("'Extracting tar {}' failed".format(link))
            nerrs=nerrs+1
            continue

        dest_path = os.path.join(archive,controller,resultname,"")

        src = income_unpack
        if os.path.exists(src):            
            shutil.move(src, dest_path)

        try:
            if os.path.islink(os.path.join(archive,controller,linkdest,resultname)):
                logger.info("Symlink Does exist")
        except Exception:
            logger.info("Cannot move symlink to {}.tar.xz from {} to {}".format(os.path.join(archive,controller,resultname), linksrc, linkdest))
            nerrs=nerrs+1
            os.remove(income)
            continue

        if(os.path.islink(income_unpack)):
            os.remove(income_unpack)
            ninfo=ninfo+1

        resultname = resultname+".tar.xz"
        src_path = os.path.join(archive,controller,linksrc,resultname)
        if os.path.exists(src_path):
            dest_path = os.path.join(archive,controller,linkdest, resultname)
            os.makedirs(dest_path)
            if os.path.exists(dest_path):
                shutil.copy(src_path, dest_path)

        if (os.listdir(dest_path) == 0):
            logger.info("Cannot move symlink from linksrc to linkdest")
            nerrs=nerrs+1
            os.remove(incoming)
            os.remove(income)
            continue

        state_list = []
        controller_path = os.path.join(archive,controller)
        controller_link = os.path.join(archive,controller,resultname)
        state_list = copy_symlinks(state_list, unpack_linkdestlist, controller_path, controller_link)
        
        totsuc, toterr = state_list[0], state_list[1]

        if toterr > 0 :
        # Count N link creations as one error since it is for handling of a
        # single tarball.
            nerrs=nerrs+1

        if totsuc > 0 :
        # We had at least one successful link state creation above.  So
        # it is safe to remove the original link, as we'll use the logs
        # to track down how to recover.
            if os.path.exists(tb):
                os.remove(tb)
            if os.path.isfile(tb):
                logger.info("Cannot remove {} link".format(tb))
                if toterr == 0 :
                    # We had other errors already counted against the total
                    # so don't bother counting this error
                    nerrs=nerrs+1
            ntb=ntb+1
            if toterr > 0 :
                # We have had some errors while processing this tar ball, so
                # count this as a partial success.
                logger.info("{}: success (partial)".format(os.path.join(controller,resultname)))
                ninfo=ninfo+1
            else:
                logger.info("{}: success".format(os.path.join(controller,resultname)))

        end_time=time()
        duration=end_time-start_time
        
        # log the success
        logger.info("{}: success - elapsed time (secs): {} - size (bytes): $size".format(os.path.join(controller,resultname),duration))
        
    return Results(ntotal=ntotal,
                   ntb=ntb,
                   nerrs=nerrs,
                   ndups=ndups,
                   ninfo=ninfo)

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
        logger.error("{}: {}".format(_NAME_, e), file=sys.stderr)
        return 1

    logger = get_pbench_logger(_NAME_, config)

    qdir = config.QDIR = config.get('pbench-server', 'pbench-quarantine-dir')

    linkdestlist = config.conf.get("pbench-server", "dispatch-states")
    linkdestlist = re.split(", |,| | ,", linkdestlist)

    if(linkdestlist is None):
        logger.info(config.timestamp(), "status : config file error: either no dispatch-states defined or a typo")
        logger.info(_NAME_,"",config.timestamp() ,"- Config file error")

    unpack_linkdestlist = config.conf.get("pbench-server", "unpacked-states")
    unpack_linkdestlist = re.split(", |,| | ,", unpack_linkdestlist)

    if(unpack_linkdestlist is None):
        logger.info(config.timestamp(), "status: config file error: either no dispatch-states defined or a typo")
        logger.info(_NAME_,"",config.timestamp() ,"- Config file error")

    logger.info('start-{}'.format(config.TS))

    counts = dispatch_unpack(config, linkdestlist, unpack_linkdestlist, logger)

    result_string = ("Total processed: {},"
                     " Result Tarballs: {},"
                     " Errors: {},"
                     " Duplicates: {},"
                     " Partially Successfull: {}"
                     .format(counts.ntotal,
                             counts.ntb,
                             counts.nerrs,
                             counts.ndups,
                             counts.ninfo))

    logger.info(result_string)

    prog = os.path.basename(sys.argv[0])

    with tempfile.NamedTemporaryFile(mode='w+t', dir=config.TMP) as reportfp:
        reportfp.write("{}.{}({})\n{}\n".format(
            prog, config.timestamp(), config.PBENCH_ENV, result_string))
        reportfp.seek(0)

        report = Report(config, _NAME_)
        report.init_report_template()
        try:
            report.post_status(config.timestamp(), "status", reportfp.name)
        except Exception:
            pass

    logger.info('end-{}'.format(config.TS))

    return 0

if __name__ == '__main__':
    status = main()
    sys.exit(status)
    
