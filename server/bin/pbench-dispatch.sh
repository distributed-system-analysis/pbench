#! /bin/bash
# -*- mode: shell-script -*-

# This script is the first part of the pipeline that processes pbench
# results tar balls.
#
# `pbench-dispatch` prepares tar balls that a version 002 SSH client submits
# for processing (`pbench-agent` v0.51 and later).  It verifies the tar balls
# and their MD5 check-sums and then moves the tar balls to the archive tree,
# setting up the appropriate state links (e.g. a production environment may
# want the tar balls unpacked (TO-UNPACK), backed up (TO-BACKUP), and indexed
# (TO-INDEX), while a satellite environment may only need to prepare the
# tar ball to be synced to the main server (TO-SYNC)).
#
# Only tar balls that have a `.md5` file are considered, since the client might
# still be in the process of sending over the tar ball (typically, the client
# writes the `.md5` file named `.md5.check` to avoid `pbench-dispatch`
# considering it while the client copies the tar ball contents over, and then
# renames it as `.md5` when the client has verified the check-sum).
#
# WARNING: it is up to the caller to make sure only one copy is running.
# Use 'flock -n $LOCKFILE /path/to/pbench-dispatch' in the crontab to
# ensure that only one copy is running. The script itself does not use
# any locking.
#
# Assumptions:
# - This script runs as a cron job
# - Tar balls and md5 check-sum files are uploaded by pbench-move/copy-results
#   to the "pbench-receive-dir-prefix" reception area.

# Load common things
. ${dir}/pbench-base.sh

# Need /usr/sbin in the PATH for `restorecon`
if [[ ! ":${PATH}:" =~ ":/usr/sbin:" ]]; then
   PATH=${PATH}:/usr/sbin; export PATH
fi

# Check that all the directories exist.
test -z "${ARCHIVE}" -o -d ${ARCHIVE} || doexit "Bad ARCHIVE=${ARCHIVE}"

errlog=${LOGSDIR}/${PROG}/${PROG}.error
mkdir -p ${LOGSDIR}/${PROG}
sts=${?}
if [[ ${sts} != 0 ]]; then
    echo "Failed: \"mkdir -p ${LOGSDIR}/${PROG}\", status ${sts}" >> ${errlog}
    exit 1
fi

linkdestlist=$(getconf.py -l dispatch-states pbench-server)
if [[ -z "${linkdestlist}" ]]; then
    echo "Failed: \"getconf.py -l dispatch-states pbench-server\"" >> ${errlog}
    exit 2
fi

# Optional "PUT API" bearer token for sending tar balls to the "new" Pbench
# Server.
put_token=$(getconf.py put-token pbench-server)

qdir=$(getconf.py pbench-quarantine-dir pbench-server)
if [[ -z "${qdir}" ]]; then
    echo "Failed: \"getconf.py pbench-quarantine-dir pbench-server\"" >> ${errlog}
    exit 2
fi
if [[ ! -d "${qdir}" ]]; then
    echo "Failed: ${qdir} does not exist, or is not a directory" >> ${errlog}
    exit 2
fi

# We are explicitly handling only version 002 data.
version="002"

receive_dir_prefix=$(getconf.py pbench-receive-dir-prefix pbench-server)
if [[ -z "${receive_dir_prefix}" ]]; then
    echo "Failed: \"getconf.py pbench-receive-dir-prefix pbench-server\"" >> ${errlog}
    exit 2
fi
receive_dir=${receive_dir_prefix}-${version}
if [[ ! -d "${receive_dir}" ]]; then
    echo "Failed: ${receive_dir} does not exist, or is not a directory" >> ${errlog}
    exit 2
fi

quarantine=${qdir}/md5-${version}
mkdir -p ${quarantine}
sts=${?}
if [[ ${sts} != 0 ]]; then
    echo "Failed: \"mkdir -p ${quarantine}\", status ${sts}" >> ${errlog}
    exit 3
fi

duplicates=${qdir}/duplicates-${version}
mkdir -p ${duplicates}
sts=${?}
if [[ ${sts} != 0 ]]; then
    echo "Failed: \"mkdir -p ${duplicates}\", status ${sts}" >> ${errlog}
    exit 3
fi

# The following directory holds tar balls that are quarantined because
# of operational errors on the server. They should be retried after
# the problem is fixed: basically, move them back into the reception
# area for 002 agents and wait.
errors=${qdir}/errors-${version}
mkdir -p ${errors}
sts=${?}
if [[ ${sts} != 0 ]]; then
    echo "Failed: \"mkdir -p ${errors}\", status ${sts}" >> ${errlog}
    exit 3
fi

log_init ${PROG}

tmp=${TMP}/${PROG}.${$}

trap 'rm -rf ${tmp}' EXIT INT QUIT

mkdir -p ${tmp}
sts=${?}
if [[ ${sts} != 0 ]]; then
    log_exit "Failed: \"mkdir -p ${tmp}\", status ${sts}" 4
fi

# Setup the report file.
status=${tmp}/status
> ${status}

# Mark the beginning of execution.
log_info ${TS}

# File that will contain the list of all .md5 files to be processed.
list=${tmp}/list.check

# Check for results that are ready for processing: version 002 agents
# upload the MD5 file as xxx.md5.check and they rename it to xxx.md5
# after they are done with MD5 checking so that's what we look for.
find ${receive_dir} -maxdepth 2 -name '*.tar.xz.md5' > ${list}.unsorted
sts=${?}
if [[ ${sts} != 0 ]]; then
    log_exit "Failed: \"find ${receive_dir} -maxdepth 2 -name '*.tar.xz.md5'\", status ${sts}" 5
fi
sort ${list}.unsorted > ${list}
sts=${?}
if [[ ${sts} != 0 ]]; then
    log_exit "Failed: \"sort ${list}.unsorted > ${list}\", status ${sts}" 6
fi

typeset -i ntotal=0
typeset -i ntbs=0
typeset -i npartialsucc=0
typeset -i nerrs=0
typeset -i ndups=0
typeset -i nquarantined=0

while read tbmd5; do
    ntotal=${ntotal}+1

    # Full pathname of tar ball
    tb=${tbmd5%.md5}

    # Controller directory path
    tbdir=$(dirname ${tb})

    # resultname: get the basename foo.tar.xz and then strip the .tar.xz
    resultname=$(basename ${tb})
    resultname=${resultname%.tar.xz}

    # The controller hostname is the last component of the directory part of
    # the full path
    controller=$(basename ${tbdir})

    dest=${ARCHIVE}/${controller}

    if [[ -f ${dest}/${resultname}.tar.xz || -f ${dest}/${resultname}.tar.xz.md5 ]]; then
        log_error "${TS}: Duplicate: ${tb} duplicate name" "${status}"
        quarantine ${duplicates}/${controller} ${tb} ${tbmd5}
        (( ndups++ ))
        continue
    fi

    pushd ${tbdir} > /dev/null 2>&4
    md5sum --check ${resultname}.tar.xz.md5
    sts=${?}
    popd > /dev/null 2>&4
    if [[ ${sts} -ne 0 ]]; then
        log_error "${TS}: Quarantined: ${tb} failed MD5 check" "${status}"
        quarantine ${quarantine}/${controller} ${tb} ${tb}.md5
        (( nquarantined++ ))
        continue
    fi

    if [[ ! -z "${put_token}" ]]; then
        # We have a bearer token for the PUT API of a "new" Pbench Server,
        # invoke the `pbench-results-push` agent CLI to send it to the
        # server (configuration of that server handled elsewhere).
        satellite=${controller%%::*}
        if [[ "${controller}" != "${satellite}" ]]; then
            metadata_arg="--metadata=server.origin:${satellite}"
        fi
        pbench-results-push ${tb} --token ${put_token} ${metadata_arg}
        sts=${?}
		if [[ ${sts} -ne 0 ]]; then
			log_info "${TS}: 'pbench-results-push ${tb} --token ${put_token} ${metadata_arg}' failed, code ${sts}" "${status}"
        fi
        unset metadata_arg
    fi

    # Make sure that all the relevant state directories exist
    mk_dirs ${controller}
    sts=${?}
    if [[ ${sts} -ne 0 ]]; then
        log_error "${TS}: Creation of ${controller} processing directories failed for ${tb}: code ${sts}" "${status}"
        (( nerrs++ ))
        continue
    fi

    # First, copy the small .md5 file to the destination. That way, if
    # that operation fails it will fail quickly since the file is small.
    cp -a ${tb}.md5 ${dest}/
    sts=${?}
    if [[ ${sts} -ne 0 ]]; then
        log_error "${TS}: Error: \"cp -a ${tb}.md5 ${dest}/\", status ${sts}" "${status}"
        (( nerrs++ ))
        continue
    fi

    # Next, mv the "large" tar ball to the destination. If the destination
    # is on the same device, the move should be quick. If the destination is
    # on a different device, the move will be a copy and delete, and will
    # take a bit longer.  If it fails, the file will NOT be at the
    # destination.
    mv ${tb} ${dest}/
    sts=${?}
    if [[ ${sts} -ne 0 ]]; then
        log_error "${TS}: Error: \"mv ${tb} ${dest}/\", status ${sts}" "${status}"
        rm ${dest}/${resultname}.tar.xz.md5
        sts=${?}
        if [[ ${sts} -ne 0 ]]; then
            log_error "${TS}: Warning: cleanup of move failure failed itself: \"rm ${dest}/${resultname}.tar.xz.md5\", status ${sts}" "${status}"
        fi
        (( nerrs++ ))
        continue
    fi

    # mv, as well as cp -a, does not restore the SELinux context properly, so
    # we do it by hand
    tbname=${resultname}.tar.xz
    restorecon ${dest}/${tbname} ${dest}/${tbname}.md5
    sts=${?}
    if [[ ${sts} -ne 0 ]]; then
        # log it but do not abort
        log_error "${TS}: Error: \"restorecon ${dest}/${tbname} ${dest}/${tbname}.md5\", status ${sts}" "${status}"
    fi

    # Now that we have successfully moved the tar ball and its .md5 to the
    # destination, we can remove the original .md5 file.
    rm ${tb}.md5
    sts=${?}
    if [[ ${sts} -ne 0 ]]; then
        log_error "${TS}: Warning: cleanup of successful copy operation failed: \"rm ${tb}.md5\", status ${sts}" "${status}"
    fi

    # Create a link in each state dir - if any fail we don't delete them
    # because we have race conditions with other cron jobs.
    let toterr=0
    let totsuc=0
    for state in ${linkdestlist}; do
        ln -sf ${dest}/${tbname} ${dest}/${state}/
        sts=${?}
        if [[ ${sts} -eq 0 ]]; then
            (( totsuc++ ))
        else
            log_error "${TS}: Cannot create ${dest}/${tbname} link to ${state}: code ${sts}" "${status}"
            (( toterr++ ))
        fi
    done
    if [[ ${toterr} -gt 0 ]]; then
        # Count N link creations as one error since it is for handling of a
        # single tar ball.
        (( nerrs++ ))
    fi
    if [[ ${totsuc} -gt 0 ]]; then
        # We had at least one successful link state creation above.
        (( ntbs++ ))
        if [[ ${toterr} -gt 0 ]]; then
            # We have had some errors while processing this tar ball, so count
            # this as a partial success.
            log_info "${TS}: ${controller}/${resultname}: success (partial)" "${status}"
            (( npartialsucc++ ))
        else
            log_info "${TS}: ${controller}/${resultname}: success" "${status}"
        fi
    fi
done < ${list}

summary_text="Processed ${ntotal} result tar balls, ${ntbs} successfully"\
" (${npartialsucc} partial), with ${nquarantined} quarantined tar balls,"\
" ${ndups} duplicately-named tar balls, and ${nerrs} errors."

log_info "${PROG}.${TS}(${PBENCH_ENV}): ${summary_text}" "${status}"

log_finish

pbench-report-status --name ${PROG} --pid ${$} --timestamp $(timestamp) --type status ${status}

exit ${nerrs}
