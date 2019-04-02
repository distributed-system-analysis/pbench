#! /bin/bash

# Cron job for user pbench, pulling tarballs from the pbench ARCHIVE and
# copying them to the configured backup directory.

# load common things
. $dir/pbench-base.sh

tmp=$TMP/${PROG}.$$
mkdir -p $tmp

stats=$tmp/stats
index_content=$tmp/index_mail_contents

trap "rm -rf $tmp" EXIT INT QUIT

log_init $PROG

# Initialize index mail content
> $index_content

echo "start-$(timestamp)"

rla=$(readlink -f $ARCHIVE)
if [[ $? -ne 0 ]]; then
    log_exit "The ARCHIVE directory does not resolve to a real location, $ARCHIVE"
fi
if [[ ! -d "$rla" ]]; then
    log_exit "The ARCHIVE directory does not resolve to a directory, $ARCHIVE"
fi

backup=$(getconf.py pbench-backup-dir pbench-server)
test ! -z $backup || log_exit "Unspecified backup directory, no pbench-backup-dir config in pbench-server section"
rlb=$(readlink -f $backup)
if [[ $? -ne 0 ]]; then
    log_exit "Specified backup directory does not resolve to a real location, $backup"
fi
if [[ ! -d "$rlb" ]]; then
    log_exit "Specified backup directory, $backup, does not resolve ($rlb) to a directory"
fi

# exclude the subdirs of symlinks
exclude="--exclude=$(echo $EXCLUDE_DIRS | sed 's/  */ --exclude=/g')"

if [ -z "$(find $rla -maxdepth 0 -type d -empty 2>/dev/null)" ] ;then
    # N.B The trailing slash is important
    rsync -va --stats $exclude $rla/ $rlb | tee -a $stats
    rsync_sts=$?
    if [[ $rsync_sts -ne 0 ]]; then
        echo "$PROG: rsync failed with code: $rsync_sts, $rlb"
    fi
fi

echo "end-$(timestamp)"

log_finish

# Back up some way and find the empty line separating the list of files
# from the stats.
cat << EOF > $index_content
$PROG.$TS($PBENCH_ENV)
EOF

if [ -e $stats ] ;then
    tail -n 20 $stats | sed -n '/^$/,$p' >> $index_content
fi

pbench-report-status --name $PROG --timestamp $TS --type status $index_content

exit 0
