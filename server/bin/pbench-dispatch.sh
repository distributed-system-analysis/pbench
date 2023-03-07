#! /bin/bash
# -*- mode: shell-script -*-

# This script is the first part of the pipeline that processes pbench result
# tar balls.
#
# `pbench-dispatch` prepares tar balls that a version 002 SSH client submits
# for processing (`pbench-agent` v0.51 and later).  It verifies the tar balls
# and their MD5 check-sums, backups them up, and then moves the tar balls to the
# archive tree, setting up the appropriate state links (e.g. a production
# environment may want the tar balls unpacked (TO-UNPACK) and indexed
# (TO-INDEX), while a satellite environment may only need to prepare the tar
# ball to be synced to the main server (TO-SYNC)).
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

# Check that all required directories specified in the environment exist.
test -d "${ARCHIVE}" || doexit "Bad ARCHIVE=${ARCHIVE}"
test -d "${LOGSDIR}" || doexit "Bad LOGSDIR=${LOGSDIR}"
install_dir=$(getconf.py install-dir pbench-server)
test -d "${install_dir}" || doexit "Bad install_dir=${install_dir}"

# If a backup directory is specified, it had better exist.
backup_dir=$(getconf.py pbench-backup-dir pbench-server)
test -z "${backup_dir}" -o -d "${backup_dir}" || doexit "Bad backup_dir=${backup_dir}"

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

bad_md5=${qdir}/md5-${version}
mkdir -p ${bad_md5}
sts=${?}
if [[ ${sts} != 0 ]]; then
    echo "Failed: \"mkdir -p ${bad_md5}\", status ${sts}" >> ${errlog}
    exit 3
fi

duplicates=${qdir}/duplicates-${version}
mkdir -p ${duplicates}
sts=${?}
if [[ ${sts} != 0 ]]; then
    echo "Failed: \"mkdir -p ${duplicates}\", status ${sts}" >> ${errlog}
    exit 3
fi

function quarantine () {
    # Function used by the shims to quarantine problematic tarballs.
    #
    # It is assumed that the function is called within a log_init/log_finish
    # context.  Errors here are fatal but we log an error message to help
    # diagnose problems.
    local _dest=${1}
    shift
    local _files="${@}"

    mkdir -p ${_dest} > /dev/null 2>&1
    local _sts=${?}
    if [[ ${_sts} -ne 0 ]]; then
        # log error
        log_exit "${TS}: quarantine ${_dest} ${_files}: \"mkdir -p ${_dest}/\" failed with status ${_sts}" 101
    fi
    local _afile
    for _afile in ${_files}; do
        if [[ ! -e ${_afile} && ! -L ${_afile} ]]; then
            continue
        fi
        mv ${_afile} ${_dest}/ > /dev/null 2>&1
        _sts=${?}
        if [[ ${_sts} -ne 0 ]]; then
            # log error
            log_exit "${TS}: quarantine ${_dest} ${_files}: \"mv ${_afile} ${_dest}/\" failed with status ${_sts}" 102
        fi
    done
}

log_init ${PROG}

tmp=${TMP}/${PROG}.${$}

trap 'rm -rf ${tmp}' EXIT INT QUIT

mkdir -p ${tmp}
sts=${?}
if [[ ${sts} != 0 ]]; then
    log_exit "Failed: \"mkdir -p ${tmp}\", status ${sts}" 4
fi

# File that will contain the list of all .md5 files to be processed.
list=${tmp}/list.check

start_ts=$(timestamp)

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

server_version="$(< ${install_dir}/VERSION)"
server_sha1="$(<${install_dir}/SHA1)"
server_hostname=$(hostname -f)

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
        log_error "${TS}: Duplicate: ${tb} duplicate name"
        quarantine ${duplicates}/${controller} ${tbmd5} ${tb}
        (( ndups++ ))
        continue
    fi

    pushd ${tbdir} > /dev/null 2>&4
    md5sum --check ${resultname}.tar.xz.md5
    sts=${?}
    popd > /dev/null 2>&4
    if [[ ${sts} -ne 0 ]]; then
        log_error "${TS}: Quarantined: ${tb} failed MD5 check"
        quarantine ${bad_md5}/${controller} ${tbmd5} ${tb}
        (( nquarantined++ ))
        continue
    fi

    if [[ -n "${backup_dir}" ]]; then
        # Backup to the local backup directory.
        mkdir -p ${backup_dir}/${controller}
        sts=${?}
        if [[ ${sts} -ne 0 ]]; then
            log_error "${TS}: failed to create backup directory ${backup_dir}/${controller}: code ${sts}"
            (( nberrs++ ))
            continue
        fi
        cp -a ${tbmd5} ${tb} ${backup_dir}/${controller}/
        sts=${?}
        if [[ ${sts} -ne 0 ]]; then
            log_error "${TS}: failed to backup ${tbmd5} and ${tb}: code ${sts}"
            (( nberrs++ ))
            continue
        fi
    fi

    if [[ ! -z "${put_token}" ]]; then
        # We have a bearer token for the PUT API of a "new" Pbench Server,
        # invoke the `pbench-results-push` agent CLI to send it to the
        # server (configuration of that server handled elsewhere).

        # All tar balls pushed to the "new" Pbench Server are made public just
        # like they are all public on the current "old" Pbench Server.
        push_options="--token ${put_token} --access=public"
        push_options+=" --metadata=global.server.legacy.version:${server_version}"
        push_options+=" --metadata=global.server.legacy.sha1:${server_sha1}"
        push_options+=" --metadata=global.server.legacy.hostname:${server_hostname}"
        satellite=${controller%%::*}
        if [[ "${controller}" != "${satellite}" ]]; then
            push_options+=" --metadata=server.origin:${satellite}"
        fi
        pbench-results-push ${tb} ${push_options}
        sts=${?}
        if [[ ${sts} -ne 0 ]]; then
            log_error "${TS}: 'pbench-results-push ${tb} ${push_options}' failed, code ${sts}"
        fi
    fi

    # Make sure that all the relevant state directories exist
    mk_dirs ${controller}
    sts=${?}
    if [[ ${sts} -ne 0 ]]; then
        log_error "${TS}: Creation of ${controller} processing directories failed for ${tb}: code ${sts}"
        (( nerrs++ ))
        continue
    fi

    # First, copy the small .md5 file to the destination. That way, if
    # that operation fails it will fail quickly since the file is small.
    cp -a ${tbmd5} ${dest}/
    sts=${?}
    if [[ ${sts} -ne 0 ]]; then
        log_error "${TS}: Error: \"cp -a ${tbmd5} ${dest}/\", status ${sts}"
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
        log_error "${TS}: Error: \"mv ${tb} ${dest}/\", status ${sts}"
        rm ${dest}/${resultname}.tar.xz.md5
        sts=${?}
        if [[ ${sts} -ne 0 ]]; then
            log_error "${TS}: Warning: cleanup of move failure failed itself: \"rm ${dest}/${resultname}.tar.xz.md5\", status ${sts}"
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
        log_error "${TS}: Error: \"restorecon ${dest}/${tbname} ${dest}/${tbname}.md5\", status ${sts}"
    fi

    # Now that we have successfully moved the tar ball and its .md5 to the
    # destination, we can remove the original .md5 file.
    rm ${tbmd5}
    sts=${?}
    if [[ ${sts} -ne 0 ]]; then
        log_error "${TS}: Warning: cleanup of successful copy operation failed: \"rm ${tbmd5}\", status ${sts}"
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
            log_error "${TS}: Cannot create ${dest}/${tbname} link to ${state}: code ${sts}"
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
            log_info "${TS}: ${controller}/${resultname}: success (partial)"
            (( npartialsucc++ ))
        else
            log_info "${TS}: ${controller}/${resultname}: success"
        fi
    fi
done < ${list}

end_ts=$(timestamp)

if [[ ${ntotal} -gt 0 ]]; then
    summary_text="Processed ${ntotal} result tar balls, ${ntbs} successfully"
    summary_text+=" (${npartialsucc} partial), with ${nquarantined} quarantined"
    summary_text+=" tar balls, ${ndups} duplicately-named tar balls, and"
    summary_text+=" ${nerrs} errors."
    printf -v summary_inner_json \
        "{\"%s\": \"%s\", \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": \"%s\", \"%s\": \"%s\"}" \
        "end_ts" "${end_ts}" \
        "errors" "${nerrs}" \
        "ndups" "${ndups}" \
        "npartialsucc" "${npartialsucc}" \
        "nquarantined" "${nquarantined}" \
        "ntbs" "${ntbs}" \
        "ntotal" "${ntotal}" \
        "prog" "${PROG}" \
        "start_ts" "${start_ts}"
    printf -v summary_json "{\"pbench\": {\"report\": {\"summary\": %s}}}" "${summary_inner_json}"

    log_info "${TS}(${PBENCH_ENV}): ${summary_text} -- @cee:${summary_json}"
fi

log_finish

exit ${nerrs}
