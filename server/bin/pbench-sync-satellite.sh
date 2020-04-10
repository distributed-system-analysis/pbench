#! /bin/bash

# Simulate what pbench-move-results does for tar balls found on a given
# satellite (remote) pbench server.

# pbench-move-results copies tarballs to the server in the reception
# areas (fs-version-001 and -002 versions), and then the respective
# shims set about moving them into place for pbench-dispatch to move
# through the various processing stages.

# This script simulates what pbench-move-results does with the
# tarballs that it copies from a satellite server. It runs as a cron
# job once a minute.

# Assumption: this script is running as user "pbench" on the master
# server and can ssh as user "pbench" to the given satellite server,
# without a password.

# load common things
case $# in
    1)
        :
        ;;
    *)
        echo "Usage: $PROG <satellite-config>" >&2
        exit 1
        ;;
esac
satellite_config=$1
shift 1
. $dir/pbench-base.sh

test -d $ARCHIVE || doexit "Bad ARCHIVE=$ARCHIVE"

remote_prefix=$(pbench-config satellite-prefix ${satellite_config})
remote_host=$(pbench-config satellite-host ${satellite_config})

tmp=$(get-tempdir-name $PROG)
unpack=$tmp/unpack.$remote_prefix
mkdir -p $unpack || doexit "Failed to create $unpack"

# Be sure $logdir is defined before setting up the trap below.
logdir_for_remote=$LOGSDIR/$PROG/$remote_prefix
logdir=$logdir_for_remote/$TS

# remove the tmp dir on exit; try to remove an empty $logdir
# but suppress any complaints (note that $logdir is a timestamped
# directory for this run.
trap "rm -rf $tmp; rmdir $logdir 2>/dev/null" EXIT QUIT INT

# The creation of the $logdir hierarchy should happen only after the
# trap so that if it fails, the $tmp directory will be cleaned up as
# well.
mkdir -p $logdir || doexit "Failed to create $logdir"

log_init $PROG

function do_remote_sat_state_change {
    local status
    pbench-remote-satellite-state-change ${satellite_config} ${state_change_log} > ${logdir}/mv.log 2>&1
    status=$?
    if [[ $status != 0 ]] ;then
        cat << EOF > $index_content
FAILED: $PROG: $remote_prefix: satellite state change failed twice.

Unable to change the state directories of tarballs, in $remote_host, due to ssh failure.
EOF
        pbench-report-status --name ${PROG} --pid ${$} --timestamp $(timestamp) --type error ${index_content}
    else
        rm ${state_change_log}
        status=$?
        if [[ $status != 0 ]]; then
            cat << EOF > $index_content
$PROG ($remote_prefix): Failed to remove local "${state_change_log}"

ssh to the $remote_host was sucessfull for changing the state of tarballs,
but failed to remove local "${state_change_log}".
EOF
            pbench-report-status --name ${PROG} --pid ${$} --timestamp $(timestamp) --type error ${index_content}
        else
            rm ${logdir}/mv.log
        fi
    fi
    return $status
}

# accumulate errors in a file for mailing at end
mail_content=$tmp/mail.log
> $mail_content
index_content=$tmp/index_mail_contents
> $index_content

let start_time=$(timestamp-seconds-since-epoch)
log_info "$TS: start - $(timestamp)" "${mail_content}"

# NOTE: the log file for tracking which tarballs have to be updated on
# the remote satellite server is shared between runs, so it is not in
# the timestamped log directory for a given satellite.
state_change_log=$logdir_for_remote/change_state.log

# check whether any previous ssh failure; if any try again here before
# we try to process any new tar balls on the satellite server.  If it
# fails again then exit without going further.
if [ -s ${state_change_log} ] ;then
    log_error "$PROG: completing previous satellite state changes ... (${state_change_log})" "${mail_content}"
    do_remote_sat_state_change
    status=$?
    if [[ $status != 0 ]]; then
        log_exit "$PROG: unable to complete previous satellite state changes (${state_change_log})"
    fi
    log_error "$PROG: completed previous satellite state changes" "${mail_content}"
else
    # initialize state change log
    > ${state_change_log}
fi

typeset -i nprocessed=0
typeset -i nfailed_md5=0
typeset -i nerrs=0

# Fetch all the tarballs from remote host's archive
pbench-remote-sync-package-tarballs ${satellite_config} ${tmp}/satellite.${remote_prefix}.tar
rc=$?
if [[ $rc != 0 ]] ;then
    log_exit "$PROG: pbench-remote-sync-package-tarballs: failed." 2
fi

if [ -s $tmp/satellite.$remote_prefix.tar ]; then
    log_info "$TS: remote tarballs fetched, unpacking ... - $(timestamp)" "${mail_content}"

    # unpack the tarball into tmp directory
    tar -xf $tmp/satellite.$remote_prefix.tar -C $unpack
    if [[ $? -ne 0 ]]; then
        cat $tmp/satellite.$remote_prefix.tar >&4
    fi
    files=$(find $unpack -path '*.tar.xz' -printf '%P\n')
    hosts="$(for host in $files;do echo ${host%%/*};done | sort -u )"

    log_info "$TS: remote tarballs unpacked - $(timestamp)" "${mail_content}"
else
    hosts=""
fi

let unpack_start_time=$(timestamp-seconds-since-epoch)

for host in $hosts ;do
    typeset -i processed=0
    typeset -i failed_md5=0
    localdir=$ARCHIVE/$remote_prefix::$host

    pushd $localdir > /dev/null 2>&1
    rc=$?
    if [ $rc -ne 0 ]; then
        mkdir -p $localdir
        rc=$?
        if [ $rc -ne 0 ]; then
            nerrs=$nerrs+1
            log_error "$PROG: failed to create remote controller in archive, $localdir" "${mail_content}"
            continue
        else
            pushd $localdir > /dev/null
            rc=$?
            if [ $rc -ne 0 ]; then
                nerrs=$nerrs+1
                log_error "$PROG: failed to pushd to remote controller in archive, $localdir" "${mail_content}"
                continue
            fi
        fi
    fi

    mkdir -p $logdir/$host
    rc=$?
    if [ $rc -ne 0 ]; then
        nerrs=$nerrs+1
        log_error "$PROG: failed to create $logdir/$host" "${mail_content}"
        continue
    fi

    # get the tarball list for this host
    flist=$(find $unpack/$host -type f -name '*.tar.xz.md5' | sed 's;'$unpack/$host/';;' | sort)

    echo $flist

    # move the unpacked files from tmp directory to archive
    mv $unpack/$host/* .

    # move prefix files if present
    if [[ -d $unpack/$host/.prefix ]] ;then
        mkdir -p ./.prefix
        mv $unpack/$host/.prefix/* ./.prefix
    fi

    # make the state dirs: TODO, TO-INDEX, TO-COPY-SOS etc.
    mk_dirs $remote_prefix::$host

    # check md5s and move md5s to its appropriate state directories according to pass or fail
    md5_list="$flist"
    md5sum -c $md5_list > $logdir/$host/md5-checks.log
    processed=$(wc -l < $logdir/$host/md5-checks.log)
    nprocessed=$((nprocessed + processed))
    grep 'OK' $logdir/$host/md5-checks.log > $logdir/$host/ok-checks.log
    if [ -s $logdir/$host/ok-checks.log ] ;then
        md5_pass=$(cat $logdir/$host/ok-checks.log | sed -n 's/: OK//p')
        for x in $md5_pass; do
            ln -sf $PWD/$x SATELLITE-MD5-PASSED/$x
            status=$?
            if [[ $status != 0 ]] ;then
                nerrs=$nerrs+1
                log_error "Failed to create the symlink for md5 check passed tarballs: ln -sf $PWD/$x SATELLITE-MD5-PASSED/$x" "${mail_content}"
                continue
            fi
        done
    fi
    grep 'FAILED' $logdir/$host/md5-checks.log > $logdir/$host/fail-checks.log
    cat $logdir/$host/fail-checks.log >> $mail_content
    failed_md5=$(wc -l < $logdir/$host/fail-checks.log)
    nfailed_md5=$((nfailed_md5 + failed_md5))
    if [ -s $logdir/$host/fail-checks.log ] ;then
        md5_fail=$(cat $logdir/$host/fail-checks.log | sed -n 's/: FAILED//p')
        for x in $md5_fail; do
            ln -sf $PWD/$x SATELLITE-MD5-FAILED/$x
            status=$?
            if [[ $status != 0 ]] ;then
                nerrs=$nerrs+1
                log_error "Failed to create the symlink for md5 check failed tarballs: ln -sf $PWD/$x SATELLITE-MD5-FAILED/$x" "${mail_content}"
                continue
            fi
        done
    fi
    # create symlinks for the synced tarballs in TODO
    if [ -s $logdir/$host/ok-checks.log ] ;then
        for x in $md5_pass; do
            ln -sf $PWD/$x TODO/$x
            status=$?
            if [[ $status != 0 ]] ;then
                nerrs=$nerrs+1
                log_error "Failed to create the symlink for TODO state directory: ln -sf $PWD/$x TODO/$x" "${mail_content}"
                continue
            fi
        done
    fi
    # save the contents of ok checks to further use it for state change
    if [ -s $logdir/$host/ok-checks.log ] ;then
        state_list=$(cat $logdir/$host/ok-checks.log | sed -n 's/: OK//p')
        for x in $state_list; do
            echo "$host/TO-SYNC/$x" >> ${state_change_log}
        done
        rm $logdir/$host/ok-checks.log
    fi

    if [[ ! -s $logdir/$host/fail-checks.log ]] ; then
        rm $logdir/$host/fail-checks.log
        grep -q -F -v 'OK' $logdir/$host/md5-checks.log
        if [[ $? -ne 0 ]]; then
            rm $logdir/$host/md5-checks.log
        fi
    fi

    rmdir ${logdir}/${host} 2>/dev/null

    popd > /dev/null 2>&4
done

# change the state of the tarballs on remote
if [ -s ${state_change_log} ] ;then
    log_error "$PROG: completing satellite state changes ... (${state_change_log})" "${mail_content}"
    do_remote_sat_state_change
    status=$?
    if [[ $status != 0 ]]; then
        log_error "$PROG: unable to complete satellite state changes (${state_change_log})" "${mail_content}"
    else
        log_error "$PROG: completed satellite state changes" "${mail_content}"
    fi
fi

let end_time=$(timestamp-seconds-since-epoch)
let duration=end_time-start_time
log_info "$TS: end - $(timestamp)" "${mail_content}"
log_info "$TS: duration (secs): $duration" "${mail_content}"
log_info "$TS: Total $nprocessed files processed, with $nfailed_md5 md5 failures and $nerrs errors" "${mail_content}"

log_finish

subj="$PROG.$TS($PBENCH_ENV) - w/ $nerrs errors"
cat << EOF > $index_content
$subj
Remote $remote_prefix: processed $nprocessed files, with $nfailed_md5 md5 failures and $nerrs errors.

EOF
cat $mail_content >> $index_content
pbench-report-status --name ${PROG} --pid ${$} --timestamp $(timestamp) --type status ${index_content}

exit 0
