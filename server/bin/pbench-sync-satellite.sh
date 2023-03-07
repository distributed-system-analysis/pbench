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

test -d "${ARCHIVE}" || doexit "Bad ARCHIVE=${ARCHIVE}"

remote_prefix=$(getconf.py satellite-prefix ${satellite_config})
remote_host=$(getconf.py satellite-host ${satellite_config})

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
    if [[ $status != 0 ]]; then
        log_error "${TS}: ${remote_prefix}: satellite state change failed twice, ssh failed to ${remote_host}"
    else
        rm ${state_change_log}
        status=$?
        if [[ $status != 0 ]]; then
            log_error "${TS}: ${remote_prefix}: Failed to remove local '${state_change_log}'"
        else
            rm ${logdir}/mv.log
        fi
    fi
    return $status
}

let start_time=$(timestamp-seconds-since-epoch)
start_ts=$(timestamp)

# NOTE: the log file for tracking which tarballs have to be updated on
# the remote satellite server is shared between runs, so it is not in
# the timestamped log directory for a given satellite.
state_change_log=$logdir_for_remote/change_state.log

# check whether any previous ssh failure; if any try again here before
# we try to process any new tar balls on the satellite server.  If it
# fails again then exit without going further.
if [ -s ${state_change_log} ]; then
    log_error "${TS}: Completing previous satellite state changes ... (${state_change_log})"
    do_remote_sat_state_change
    status=$?
    if [[ $status != 0 ]]; then
        log_exit "${TS}: unable to complete previous satellite state changes (${state_change_log})"
    fi
    log_error "${TS}: completed previous satellite state changes"
else
    # initialize state change log
    > ${state_change_log}
fi

typeset -i nhosts=0
typeset -i ntotal=0
typeset -i nprocessed=0
typeset -i nerrs=0

syncerr=${tmp}/syncerrors

# Fetch all the tarballs from remote host's archive
pbench-remote-sync-package-tarballs ${satellite_config} ${tmp}/satellite.${remote_prefix}.tar ${syncerr}
rc=$?
if [[ $rc != 0 ]]; then
    log_exit "${TS}: FAILED -- $(cat ${syncerr})" 2
fi

if [ -s $tmp/satellite.$remote_prefix.tar ]; then
    # Unpack the tarball into tmp directory, logging any errors reported.
    tar -xf $tmp/satellite.$remote_prefix.tar -C $unpack
    if [[ $? -ne 0 ]]; then
        cat $tmp/satellite.$remote_prefix.tar >&4
    fi
    files=$(find $unpack -path '*.tar.xz' -printf '%P\n')
    hosts="$(for host in $files;do echo ${host%%/*};done | sort -u )"
else
    hosts=""
fi

dest=$(getconf.py pbench-receive-dir-prefix pbench-server)-002
let unpack_start_time=$(timestamp-seconds-since-epoch)

for host in $hosts ;do
    (( nhosts++ ))
    localdir=$dest/$remote_prefix::$host

    pushd $localdir > /dev/null 2>&1
    rc=$?
    if [ $rc -ne 0 ]; then
        mkdir -p $localdir
        rc=$?
        if [ $rc -ne 0 ]; then
            (( nerrs++ ))
            log_error "${TS}: failed to create remote controller in archive, $localdir"
            continue
        else
            pushd $localdir > /dev/null
            rc=$?
            if [ $rc -ne 0 ]; then
                (( nerrs++ ))
                log_error "${TS}: failed to pushd to remote controller in archive, $localdir"
                continue
            fi
        fi
    fi

    # Get the tarball list for this host.
    find $unpack/$host -type f -name '*.tar.xz.md5' | sort > $tmp/$host.tb.lis

    # Loop over the .MD5 files, first moving the tar balls into the regular
    # reception area, since no tar ball will be processed in the reception area
    # without a .md5 file present, then moving the .md5 files into place, and
    # recording success for updating the remote host.
    while read tbmd5; do
        (( ntotal++ ))
        mv ${tbmd5%*.md5} ./
        status=$?
        if [[ $status != 0 ]]; then
           (( nerrs++ ))
            log_error "Failure moving tar ball ${tbmd5%*.md5} to $localdir"
            continue
        fi
        mv ${tbmd5} ./
        status=$?
        if [[ $status != 0 ]]; then
            rm -f ${tbmd5%*.md5}
            (( nerrs++ ))
            log_error "Failure moving tar ball MD5 file ${tbmd5} to $localdir"
            continue
        fi
        echo "$host/TO-SYNC/$(basename ${tbmd5%*.md5})" >> ${state_change_log}
        nprocessed=$nprocessed+1
    done < $tmp/$host.tb.lis

    popd > /dev/null 2>&4
done

# change the state of the tarballs on remote
if [ -s ${state_change_log} ]; then
    log_error "$PROG: completing satellite state changes ... (${state_change_log})"
    do_remote_sat_state_change
    status=$?
    if [[ $status != 0 ]]; then
        log_error "$PROG: unable to complete satellite state changes (${state_change_log})"
    else
        log_error "$PROG: completed satellite state changes"
    fi
fi

let end_time=$(timestamp-seconds-since-epoch)
end_ts=$(timestamp)
let duration=end_time-start_time

if [[ ${nhosts} -gt 0 ]]; then
    summary_text="(${PBENCH_ENV})"
    summary_text+=" ${remote_prefix} Processed ${nprocessed} files (from"
    summary_text+=" ${nhosts} hosts, ${ntotal} total tar balls), with ${nerrs}"
    summary_text+=" errors, in ${duration} seconds"
    printf -v summary_inner_json \
        "{\"%s\": %d, \"%s\": \"%s\", \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": \"%s\", \"%s\": \"%s\", \"%s\": \"%s\", \"%s\": \"%s\"}" \
        "duration" "${duration}" \
        "end_ts" "${end_ts}" \
        "errors" "${nerrs}" \
        "nhosts" "${nhosts}" \
        "nprocessed" "${nprocessed}" \
        "ntotal" "${ntotal}" \
        "prog" "${PROG}" \
        "remote_prefix" "${remote_prefix}" \
        "start_ts" "${start_ts}" \
        "text" "${summary_text}"
    printf -v summary_json "{\"pbench\": {\"report\": {\"summary\": %s}}}" "${summary_inner_json}"

    log_info "@cee:${summary_json}"
fi
log_finish

exit 0
