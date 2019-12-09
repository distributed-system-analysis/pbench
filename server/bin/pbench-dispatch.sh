#! /bin/bash
# -*- mode: shell-script -*-

# This script is the first part of the pipeline that processes pbench
# results tarballs.

# First stage:  pbench-dispatch looks in all the TODO directories,
#               checks MD5 sums and creates symlinks in all the state
#               directories for the particular environment where this
#               server runs (e.g. for the production environment, links
#               are created in the TO-UNPACK, TO-INDEX, TO-COPY-SOS and
#               TO-BACKUP directories; for a satellite, it will only
#               create links in the TO-UNPACK and TO-SYNC directories).
#               Then the symlink in TODO is deleted: we don't want to
#               deal with this tarball again; but if there are recover-
#               able errors, we may keep it in TODO and try again later.
#               Any errors are reported for possible action by an admin.
#

# assumptions:
# - this script runs as a cron job
# - tarballs and md5 sums are uploaded by pbench-move/copy-results to
#   $ARCHIVE/$(hostname -s) area.
# FIXME: the above should be to the reception area ...
# - pbench-move/copy-results also makes a symlink to each tarball it
#   uploads in $ARCHIVE/TODO, thereby telling this script to process
#   the tarball.
# FIXME: the pbench shims do that now ...

# load common things
. $dir/pbench-base.sh

# check that all the directories exist
test -d $ARCHIVE || doexit "Bad ARCHIVE=$ARCHIVE"
test -d $UNPACK_DIR || doexit "Bad UNPACK=$UNPACK_DIR"

tmp=$TMP/$PROG.$$

trap 'rm -rf $tmp' EXIT INT QUIT
mkdir -p $tmp || doexit "Failed to create $tmp"

log_init $PROG

# WARNING: it is up to the caller to make sure only one copy is running.
# Use 'flock -n $LOCKFILE /path/to/pbench-dispatch' in the crontab to
# ensure that only one copy is running. The script itself does not use
# any locking.

# the link source and destination for this script
linksrc=TODO
linkdestlist=$(getconf.py -l dispatch-states pbench-server)

mail_content=$tmp/mail_content.log
index_content=$tmp/index_mail_contents

# Initialize index mail content
> $index_content
> $mail_content

if [ -z "$linkdestlist" ]; then
    log_error "$TS: config file error: either no dispach-states defined or a typo"
    subj="$PROG.$TS($PBENCH_ENV) - Config file error"
    cat << EOF > $index_content
$subj
config file error: either no dispach-states defined or a typo
EOF
    pbench-report-status --name ${PROG} --pid ${$} --timestamp $(timestamp) --type error ${index_content}
    log_finish
    exit 1
fi

log_info $TS

# Find all the links in all the $ARCHIVE/<controller>/$linksrc
# directories, emitting a list of their full paths with the size
# in bytes of the file the link points to, and then sort them so
# that we process the smallest tar balls first.
list=$tmp/list
> ${list}.unsorted
# First we find all the $linksrc directories
for linksrc_dir in $(find $ARCHIVE/ -maxdepth 2 -type d -name $linksrc); do
    # Find all the links in a given $linksrc directory that are
    # links to actual files (bad links are not emitted!).
    find -L $linksrc_dir -type f -name '*.tar.xz' -printf "%p\n" 2>/dev/null >> ${list}.unsorted
    # Find all the links in the same $linksrc directory that don't
    # link to anything so that we can count them as errors below.
    find -L $linksrc_dir -type l -name '*.tar.xz' -printf "%p\n" 2>/dev/null >> ${list}.unsorted
done
# Simple alphabetical sort
sort ${list}.unsorted > ${list}
rm -f ${list}.unsorted

typeset -i ntb=0
typeset -i ntotal=0
typeset -i nerrs=0
typeset -i ndups=0
typeset -i npartialsucc=0

while read tarball ;do
    let ntotal+=1

    linksrc_path=$(dirname $tarball)
    tb_linksrc=$(basename $linksrc_path)
    if [ "$linksrc" != "$tb_linksrc" ]; then
        # All is NOT well: we expect $linksrc as the parent directory name
        # of the symlink tarball name.
        log_exit "$TS: FATAL - unexpected \$linksrc for $tarball" 57
    fi

    controller_path=$(dirname $linksrc_path)
    controller=$(basename $controller_path)
    if [ "$ARCHIVE" != "$(dirname $controller_path)" ]; then
        # The controller's parent is not $ARCHIVE!
        log_exit "$TS: FATAL - unexpected archive directory for $tarball" 57
    fi

    link=$(readlink -e $tarball)
    if [ -z "$link" ] ;then
        log_error "$TS: symlink target for $tarball does not exist" "${mail_content}"
        let nerrs+=1
        quarantine ${controller_path}/_QUARANTINED/BAD-LINK ${tarball}
        continue
    fi

    resultname=$(basename $tarball)
    resultname=${resultname%.tar.xz}

    # XXXX - for now, if it's a duplicate name, just punt and avoid
    # producing the error
    if [ ${resultname%%.*} == "DUPLICATE__NAME" ] ;then
        let ndups+=1
        quarantine ${controller_path}/_QUARANTINED/DUPLICATES ${link} ${link}.md5 ${controller_path}/.prefix/${resultname}.prefix
        rm -f ${tarball}
        status=$?
        if [ $status -ne 0 ] ;then
            log_error "$TS: Cannot remove $tarball link: code $status" "${mail_content}"
        fi
        continue
    fi

    # make sure that all the relevant state directories exist
    mk_dirs $controller
    status=$?
    if [ $status -ne 0 ] ;then
        log_error "$TS: Creation of $controller processing directories failed for $tarball: code $status" "${mail_content}"
        let nerrs+=1
        continue
    fi

    pushd ${controller_path} > /dev/null 2>&4
    md5sum --check ${resultname}.tar.xz.md5
    sts=$?
    popd >/dev/null 2>&4
    if [ $sts -ne 0 ] ;then
        log_error "$TS: MD5 check of ${link} failed for ${tarball}" "${mail_content}"
        quarantine ${controller_path}/_QUARANTINED/BAD-MD5 ${link} ${link}.md5 ${controller_path}/.prefix/${resultname}.prefix
        rm -f ${tarball}
        status=$?
        if [ $status -ne 0 ] ;then
            log_error "$TS: Cannot remove $tarball link: code $status" "${mail_content}"
        fi
        let nerrs+=1
        continue
    fi

    # create a link in each state dir - if any fail, we should delete them all? No, that
    # would be racy.
    let toterr=0
    let totsuc=0
    for state in $linkdestlist ;do
        ln -sf $link ${controller_path}/${state}/
        status=$?
        if [ $status -eq 0 ] ;then
            let totsuc+=1
        else
            log_error "$TS: Cannot create $tarball link to $state: code $status" "${mail_content}"
            let toterr+=1
        fi
    done
    if [ $toterr -gt 0 ]; then
        # Count N link creations as one error since it is for handling of a
        # single tarball.
        let nerrs+=1
    fi
    if [ $totsuc -gt 0 ]; then
        # We had at least one successful link state creation above.  So
        # it is safe to remove the original link, as we'll use the logs
        # to track down how to recover.
        rm -f $tarball
        status=$?
        if [ $status -ne 0 ] ;then
            log_error "$TS: Cannot remove $tarball link: code $status" "${mail_content}"
            if [ $toterr -eq 0 ]; then
                # We had other errors already counted against the total
                # so don't bother counting this error
                let nerrs+=1
            fi
        fi
        let ntb+=1
        if [ $toterr -gt 0 ]; then
            # We have had some errors while processing this tar ball, so
            # count this as a partial success.
            log_info "$TS: $controller/$resultname: success (partial)"
            let npartialsucc+=1
        else
            log_info "$TS: $controller/$resultname: success"
        fi
    fi
done < $list

summary_text="Processed $ntotal result tar balls, $ntb successfully ($npartialsucc partial), with $nerrs errors, and $ndups duplicates"

log_info "$TS: $summary_text"

log_finish

subj="$PROG.$TS($PBENCH_ENV) - w/ $nerrs errors"
cat << EOF > $index_content
$subj
$summary_text

EOF
cat $mail_content >> $index_content
pbench-report-status --name ${PROG} --pid ${$} --timestamp $(timestamp) --type status ${index_content}

exit 0
