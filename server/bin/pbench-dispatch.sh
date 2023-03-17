#! /bin/bash
# -*- mode: shell-script -*-

# This script is the first part of the pipeline that processes pbench result tar
# balls.
#
# `pbench-dispatch` prepares tar balls that a version 002 SSH client submits for
# processing (`pbench-agent` v0.51 and later).  It verifies the tar balls and
# their MD5 check-sums, backs them up, and then pushes the tar balls to the
# configured "new" (v0.72+) Pbench Server using the PUT API.
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
test -d "${LOGSDIR}" || doexit "Bad LOGSDIR=${LOGSDIR}"
install_dir=$(pbench-server-config install-dir pbench-server)
test -d "${install_dir}" || doexit "Bad install_dir=${install_dir}"
backup_dir=$(pbench-server-config pbench-backup-dir pbench-server)
test -d "${backup_dir}" || doexit "Bad backup_dir=${backup_dir}"
unpack_dir=$(pbench-server-config pbench-unpack-dir pbench-server)
test -d "${unpack_dir}" || doexit "Bad unpack_dir=${unpack_dir}"

log_init ${PROG}

mkdir -p ${LOGSDIR}/${PROG}
sts=${?}
if [[ ${sts} != 0 ]]; then
    log_exit "${TS}: Failed: \"mkdir -p ${LOGSDIR}/${PROG}\", status ${sts}"
fi

# Optional "PUT API" bearer token for sending tar balls to the "new" Pbench
# Server.
put_token=$(pbench-server-config put-token pbench-server)
if [[ -z "${put_token}" ]]; then
    log_exit "${TS}: Failed: \"pbench-server-config put-token pbench-server\"" 2
fi
agent_profile=$(pbench-server-config agent-profile pbench-server)
if [[ ! -e "${agent_profile}" ]]; then
    log_exit "${TS}: Failed: PUT API token provided but no pbench-agent profile" 2
fi
source ${agent_profile}

qdir=$(pbench-server-config pbench-quarantine-dir pbench-server)
if [[ -z "${qdir}" ]]; then
    log_exit "${TS}: Failed: \"pbench-server-config pbench-quarantine-dir pbench-server\"" 2
fi
if [[ ! -d "${qdir}" ]]; then
    log_exit "${TS}: Failed: ${qdir} does not exist, or is not a directory" 2
fi

# We are explicitly handling only version 002 data.
version="002"

receive_dir_prefix=$(pbench-server-config pbench-receive-dir-prefix pbench-server)
if [[ -z "${receive_dir_prefix}" ]]; then
    log_exit "${TS}: Failed: \"pbench-server-config pbench-receive-dir-prefix pbench-server\"" 2
fi
receive_dir=${receive_dir_prefix}-${version}
if [[ ! -d "${receive_dir}" ]]; then
    log_exit "${TS}: Failed: ${receive_dir} does not exist, or is not a directory" 2
fi

bad_md5=${qdir}/md5-${version}
mkdir -p ${bad_md5}
sts=${?}
if [[ ${sts} != 0 ]]; then
    log_exit "${TS}: Failed: \"mkdir -p ${bad_md5}\", status ${sts}" 3
fi

duplicates=${qdir}/duplicates-${version}
mkdir -p ${duplicates}
sts=${?}
if [[ ${sts} != 0 ]]; then
    log_exit "${TS}: Failed: \"mkdir -p ${duplicates}\", status ${sts}" 3
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

# Check for results that are ready for processing: version 002 agents upload the
# MD5 file as xxx.md5.check and they rename it to xxx.md5 after they are done
# with MD5 checking so that's what we look for.
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

function backup_file {
    # Backup a tar ball and its .md5 file
    #
    # Assumes the caller has already verified that the source tar ball has an
    # a .md5 file and that its check-sum matches.
    #
    # Args:
    #     src : full path of source tar ball
    #     dst : full path of destination directory
    #
    # Returns:
    #     0 on success when both tar ball and its .md5 file are backed up or
    #         are already present
    local src=${1}
    local src_n=$(basename "${src}")
    local dst=${2}
    local sts

    if [[ -f ${dst}/${src_n} && -f ${dst}/${src_n}.md5 ]]; then
        # A tar ball and .md5 of the same name exist in the destination
        # directory, verify the .md5 files are the same to determine if it is
        # already backed up.
        diff -q ${src}.md5 ${dst}/ > /dev/null 2>&1 && return 0
    fi

    # Either nothing is backed up or we have a partial backup, just assume it
    # is nothing.
    if [[ ! -d ${dst} ]]; then
        mkdir ${dst} || return ${?}
    fi
    cp -a ${src}.md5 ${src} ${dst}/
}

server_version="$(< ${install_dir}/VERSION)"
server_sha1="$(<${install_dir}/SHA1)"
server_hostname=$(hostname -f)

# Total number of tar balls touched.
typeset -i ntotal=0
# Total number of tar balls successfully backed up, pushed via PUT API
typeset -i ntbs=0
# Total number of errors encountered
typeset -i nerrs=0
# Total number of tar balls quarantined due to MD5 check-sum errors
typeset -i nquarantined=0
# Total number of errors related to backing up tar balls
typeset -i nberrs=0
# Total number of errors related to setting up unpack tar balls
typeset -i nuerrs=0

while read tbmd5; do
    # Count the number of tar balls we process.
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

    pushd ${tbdir} > /dev/null 2>&4
    md5sum --check ${resultname}.tar.xz.md5
    sts=${?}
    popd > /dev/null 2>&4
    if [[ ${sts} -ne 0 ]]; then
        log_warn "${TS}: Quarantined: ${tb} failed MD5 check"
        quarantine ${bad_md5}/${controller} ${tbmd5} ${tb}
        (( nquarantined++ ))
        continue
    fi

    # We will only move a tar ball out of the reception area when it is both
    # successfully backed up & archived via `pbench-results-push`.
    let state=0

    backup_dest=${backup_dir}/${controller}
    backup_file ${tb} ${backup_dest}
    sts=${?}
    if [[ ${sts} -eq 0 ]]; then
        (( state++ ))
    else
        log_error "${TS}: failed to backup ${tb} to ${backup_dest}/: code ${sts}"
        (( nberrs++ ))
    fi

    # We have a bearer token for the PUT API of a "new" Pbench Server, invoke
    # the `pbench-results-push` agent CLI to send it to the server
    # (configuration of that server handled elsewhere).

    # All tar balls pushed to the "new" Pbench Server are made public just like
    # they are all public on the current "old" Pbench Server.
    push_options="--token ${put_token} --access=public"
    push_options+=" --metadata=global.server.legacy.version:${server_version}"
    push_options+=" --metadata=global.server.legacy.sha1:${server_sha1}"
    push_options+=" --metadata=global.server.legacy.hostname:${server_hostname}"
    satellite=${controller%%::*}
    if [[ "${controller}" != "${satellite}" ]]; then
        push_options+=" --metadata=server.origin:${satellite}"
    fi
    output=$(pbench-results-push ${tb} ${push_options} 2>&1)
    sts=${?}
    if [[ ${sts} -eq 0 ]]; then
        log_debug "${TS}: 'pbench-results-push ${tb} ${push_options}' succeeded, output '${output}'"
        (( state++ ))
    else
        log_error "${TS}: 'pbench-results-push ${tb} ${push_options}' failed, code ${sts}, output '${output}'"
        (( nerrs++ ))
        continue
    fi

    if [[ ${state} -ne 2 ]]; then
        # One or both of the above operations failed, don't bother moving the
        # tar ball to be unpacked.
        continue
    fi

    # Move tar ball to the unpack directory.
    unpack_dest=${unpack_dir}/${controller}
    if [[ ! -d ${unpack_dest} ]]; then
        mkdir ${unpack_dest}
        sts=${?}
        if [[ ${sts} -ne 0 ]]; then
            log_error "${TS}: failed to create unpack directory ${unpack_dest}: code ${sts}"
            (( nuerrs++ ))
            # NOTE WELL: we are leaving the tar ball and its .md5 in the
            # reception area since the backup operation and the archive via the
            # PUT API are idempotent and we'd like for an admin to clear this
            # situation so that a restart of this script will continue with all
            # the tar balls that failed.
            continue
        fi
    fi
    mv ${tbmd5} ${tb} ${unpack_dest}/
    sts=${?}
    if [[ ${sts} -ne 0 ]]; then
        log_error "${TS}: failed to move ${tb} and its .md5 to the unpack directory, ${unpack_dest}/: code ${sts}"
        (( nuerrs++ ))
    fi
    # Even if we fail to move to the unpack directory we just remove the tar
    # ball from the reception area to avoid spamming duplicates via the PUT API..
    rm -f ${tbmd5} ${tb}

    # Tally the successfully processed tar balls.
    (( ntbs++ ))
done < ${list}

end_ts=$(timestamp)

if [[ ${ntotal} -gt 0 ]]; then
    summary_text="(${PBENCH_ENV})"
    summary_text+=" Processed ${ntotal} result tar balls, ${ntbs} successfully,"
    summary_text+=" with ${nquarantined} quarantined, ${nberrs} backup errors,"
    summary_text+=" ${nuerrs} unpack setup errors, and ${nerrs} archive API"
    summary_text+=" errors."
    printf -v summary_inner_json \
        "{\"%s\": \"%s\", \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": \"%s\", \"%s\": \"%s\", \"%s\": \"%s\"}" \
        "end_ts" "${end_ts}" \
        "errors" "${nerrs}" \
        "nberrs" "${nberrs}" \
        "nquarantined" "${nquarantined}" \
        "ntbs" "${ntbs}" \
        "ntotal" "${ntotal}" \
        "nuerrs" "${nuerrs}" \
        "prog" "${PROG}" \
        "start_ts" "${start_ts}" \
        "text" "${summary_text}"
    printf -v summary_json "{\"pbench\": {\"report\": {\"summary\": %s}}}" "${summary_inner_json}"

    log_info "@cee:${summary_json}"
fi

log_finish

exit $(( nberrs + nerrs + nuerrs ))
