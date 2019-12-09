#! /bin/bash
# -*- mode: shell-script -*-

# This script is modelled after the pipeline that processes pbench
# results tarballs, but is standalone. It only processes edit-prefix
# requests: it looks for links in  $ARCHIVE/$hostname/TO-LINK and
# processes the edit-prefix requests in $ARCHIVE/$hostname/.prefix that
# correspond to the link. Each request moves a link from one place to
# another in the results/ hierarchy.

# - this script runs as a cron job, recommended once a minute

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
test -d $RESULTS || doexit "Bad RESULTS=$RESULTS"

log_init $PROG

# make sure only one copy is running.
# Use 'flock -n $LOCKFILE /home/pbench/bin/pbench-unpack-tarballs' in the
# crontab to ensure that only one copy is running. The script itself
# does not use any locking.

# the link source for this script
linksrc=TO-LINK

log_info "$TS"

# get the list of files we'll be operating on
list=$(ls $ARCHIVE/*/$linksrc/*.tar.xz 2>/dev/null)

typeset -i nep=0

for result in $list ;do
    link=$(readlink -e $result)
    if [ ! -f $link ] ;then
        log_error "$TS: $link does not exist" 
        continue
    fi

    resultname=$(basename $result)
    hostname=$(basename $(dirname $link))

    # echo $link
    # echo $resultname
    # echo $hostname
    # continue

    # make sure that all the relevant state directories exist
    mk_dirs $hostname

    # find the prefix file and execute it - all the checking was done on the client
    prefix=$ARCHIVE/$hostname/.prefix/prefix.${resultname%.tar.xz}
    log_info $prefix
    cmds=$(cat $prefix)
    log_info $cmds
    pushd $RESULTS/$hostname > /dev/null 2>&4
    eval "$cmds"
    status=$?
    if [ $status -ne 0 ] ;then
        log_error "$TS: eval $cmds failed - code $status" 
        continue
    fi
    popd > /dev/null 2>&4

    # remove the link from TO-LINK
    rm $result
    status=$?
    if [ $status -ne 0 ] ;then
        log_error "$TS: Cannot remove $result link from $linksrc: code $status" 
        continue
    fi

    # log the success
    log_info "$TS: $hostname/$resultname: success - processed $result"
    nep=$nep+1
done

log_info "$TS: Processed $nep edit-prefix requests"

log_finish
exit 0
