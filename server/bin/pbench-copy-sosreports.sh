#! /bin/bash
# -*- mode: shell-script -*-

# This script is the second part of the pipeline that processes pbench
# results tarballs.

# First stage:  pbench-unpack-tarballs looks in all the TODO
#               directories, unpacks tarballs, checks MD5 sums and
#               moves the symlink from the TODO subdir to the
#               TO-COPY-SOS subdir.  It runs under cron once a minute
#               in order to minimize the delay between uploading the
#               results and making them available for viewing over the
#               web.

# Second stage: pbench-copy-sosreports looks in all the TO-COPY-SOS
#               subdirs, extracs the sos report from the tarball and
#               copies it to the VoS incoming area for further
#               processing. Assuming that all is well, it moves the
#               symlink from the TO-COPY-SOS subdir to the TO-INDEX
#               subdir.

# Third stage:  pbench-index looks in all the TO-INDEX subdirs and
#               calls the pbench-results-indexer script to index the
#               results tarball into ES. It then moves the symlink from
#               the TO-INDEX subdir to the DONE subdir.

# assumptions:

# - this script runs as a cron job, recommended to run once an hour.

# - tarballs and md5 sums are uploaded by move/copy-results to
#    $ARCHIVE/$(hostname -s) area.
# - move/copy-results also makes a symlink to each tarball it uploads
#    in $ARCHIVE/$(hostname -s)/TODO.
# - pbench-unpack-tarballs processes each tarbal and moves the symlink
#    from the TODO area to the TO-COPY-SOS area.

# load common things
. $dir/pbench-base.sh

# check that all the directories exist
test -d $ARCHIVE || doexit "Bad ARCHIVE=$ARCHIVE"
test -d $INCOMING || doexit "Bad INCOMING=$INCOMING"

TMPDIR=$TMP/$PROG.$$
trap "rm -rf $TMPDIR" EXIT INT QUIT
mkdir -p $TMPDIR || doexit "Failed to create $TMPDIR"

log_init $PROG

# make sure only one copy is running.
# Use 'flock -n $LOCKFILE /home/pbench/bin/pbench-unpack-tarballs' in the
# crontab to ensure that only one copy is running. The script itself
# does not use any locking.

# the link source and destination for this script
linksrc=TO-COPY-SOS
linkdest=COPIED-SOS

if [ "$SOSREPORTDEST" == "" ]; then
    _sosrpt_user=$(pbench-config user sosreports)
    _sosrpt_host=$(pbench-config host sosreports)
    _sosrpt_dir=$(pbench-config dir sosreports)
    SOSREPORTDEST=$_sosrpt_user@$_sosrpt_host:$_sosrpt_dir/
fi

log_info "$TS: starting at $(timestamp)"

# get the list of files we'll be operating on
list=$(ls $ARCHIVE/*/$linksrc/*.tar.xz 2>/dev/null)

typeset -i nresults=0
typeset -i ntotal=0
typeset -i nerrs=0

index_content=$TMPDIR/index_mail_contents

# Initialize index mail content
> $index_content

for result in $list ;do
    link=$(readlink -e $result)
    if [ ! -f $link ] ;then
        log_error "$TS: $link does not exist"
        nerrs=$nerrs+1
        continue
    fi

    resultname=$(basename $result)
    resultname=${resultname%.tar.xz}
    hostname=$(basename $(dirname $link))

    # echo $link
    # echo $resultname
    # echo $hostname
    # continue

    # make sure that all the relevant state directories exist
    mk_dirs $hostname

    # the tarball is already unpacked, so go to the appropriate place
    # and find all the sosreports under it. This should be quick!

    incoming=$INCOMING/$hostname/$resultname

    typeset -i nsr=0
    # we look in a few places for the sysinfo/ dir, because we support
    # multiple versions of the pbench RPM, where the sysinfo/ directory
    # was located at different places in the hierarchy.
    sosreports=$(find $incoming/sysinfo $incoming/*/sysinfo $incoming/*/*/sysinfo -name 'sosreport*.tar.xz' 2>/dev/null)
    src=""
    for x in $sosreports ;do
        # sosreport should be RO
        chmod 444 $x
        if [ ! -f $x.md5 ] ;then
            log_error "$TS: FAILED: no MD5 file found for $x"
            nerrs=$nerrs+1
            continue
        fi
        chmod 444 $x.md5
        md5=$(md5sum $x)
        md5=${md5%% *}
        if [ "$md5" != $(cat $x.md5) ] ;then
            log_error "$TS: FAILED: MD5 does not match for  $x"
            nerrs=$nerrs+1
            continue
        fi
        # copy them to a temp dir
        cp "$x" "$x".md5 $TMPDIR/
        sts=$?
        if [[ $sts -ne 0 ]] ;then
            log_error "$TS: FAILED: cp "$x" "$x".md5 $TMPDIR/ - code $sts"
            nerrs=$nerrs+1
            continue
        fi
        nsr=$nsr+1
    done

    if [[  $nsr == 0 ]] ;then
        log_info "$TS: No sosreports found for $result"
    else
        pushd $incoming > /dev/null 2>&4
        cmd="/usr/bin/rsync -av $TMPDIR/ $SOSREPORTDEST"
        log_info "$TS: $cmd"
        $cmd
        sts=$?
        if [[ $sts -ne 0 ]] ;then
            log_error "$TS: FAILED: $cmd - code $sts"
            nerrs=$nerrs+1
            continue
        fi
        popd > /dev/null 2>&4
    fi

    # move the link to $linkdest directory
    mv $result $(echo $result | sed "s/$linksrc/$linkdest/")
    sts=$?
    if [[ $sts -ne 0 ]] ;then
        log_error "$TS: Cannot move $result link from $linksrc to $linkdest: code $sts"
        nerrs=$nerrs+1
        continue
    fi

    # log the success
    log_info "$TS: $hostname/$resultname: processed $nsr sosreports for $result"
    ntotal=$ntotal+$nsr
    nresults=$nresults+1
done

log_info "$TS: ending at $(timestamp), processed $ntotal sosreports for $nresults results directories with $nerrs errors"

log_finish

if [[ $nerrs -gt 0 ]]; then
    subj="$PROG.$TS($PBENCH_ENV) - w/ $nerrs errors"
else
    subj="$PROG.$TS($PBENCH_ENV)"
fi
cat << EOF > $index_content
$subj
Processed $ntotal sosreports for $nresults results directories with $nerrs errors
EOF
pbench-report-status --name ${PROG} --pid ${$} --timestamp $(timestamp) --type status ${index_content}

exit 0
