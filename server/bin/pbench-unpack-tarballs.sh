#! /bin/bash
# -*- mode: shell-script -*-

# This script is the first part of the pipeline that processes pbench
# results tar balls.

# `pbench-unpack-tarballs` looks in all the TO-UNPACK or TO-RE-UNPACK
# directories, unpacks tar balls, and moves the symlink from the TO-[RE-]UNPACK
# subdir to the UNPACKED subdir.  It runs under cron once a minute in order to
# minimize the delay between uploading the results and making them available for
# viewing via the web server.

# This script loops over the contents of ${ARCHIVE}/<controller>/TO-[RE-]UNPACK
# and unpacks each tar ball into .../incoming/<controller>/, establishing the
# proper .../results and .../users symlinks to it.  If everything works, it then
# moves the tar ball symlink from ${ARCHIVE}/TO-[RE-]UNPACK to
# ${ARCHIVE}/UNPACKED to mark the process complete.

BUCKET="${1:-none}"
PIPELINE="${2}"

if [[ "${PIPELINE}" == "re-unpack" ]]; then
    export PROG="pbench-re-unpack-tarballs"
fi
if [[ "${BUCKET}" != "none" ]]; then
    # We rename the PROG to include the bucket since we don't want to conflict
    # with other unpack tar balls running using different buckets at the same
    # time.
    export PROG="${PROG}-${BUCKET}"
fi

# load common things
. ${dir}/pbench-base.sh

# check that all the directories exist
test -d "${ARCHIVE}"  || doexit "Bad ARCHIVE=${ARCHIVE}"
test -d "${INCOMING}" || doexit "Bad INCOMING=${INCOMING}"
test -d "${RESULTS}"  || doexit "Bad RESULTS=${RESULTS}"
test -d "${USERS}"    || doexit "Bad USERS=${USERS}"

# The base destinations for this script are always the following:
linkdest=UNPACKED
linkerr=WONT-UNPACK

if [[ "${BUCKET}" == "none" ]]; then
    lb_arg=""
    ub_arg=""
    lowerbound=0
    upperbound=""
else
    lowerbound=$(pbench-server-config lowerbound pbench-unpack-tarballs/${BUCKET})
    if [[ -z "${lowerbound}" ]]; then
        lb_arg=""
        lowerbound=0
    else
        # Convert megabytes to bytes
        lowerbound=$(( ${lowerbound} * 1024 * 1024 ))
        lb_arg="-size +$(( ${lowerbound} - 1 ))c"
    fi
    upperbound=$(pbench-server-config upperbound pbench-unpack-tarballs/${BUCKET})
    if [[ -z "${upperbound}" ]]; then
        ub_arg=""
    else
        # Convert megabytes to bytes
        upperbound=$(( ${upperbound} * 1024 * 1024 ))
        ub_arg="-size -$(( ${upperbound} ))c"
    fi
fi

if [[ "${PIPELINE}" == "re-unpack" ]]; then
    # The link source for re-unpacking.
    linksrc=TO-RE-UNPACK
else
    # The link source for normal flow of unpacking.
    linksrc=TO-UNPACK
fi

tmp=${TMP}/${PROG}.${$}
trap 'rm -rf ${tmp}' EXIT INT QUIT

mkdir -p ${tmp} || doexit "Failed to create ${tmp}"

log_init ${PROG}

start_ts=$(timestamp)

# The list of files we'll be operating on, when complete, sorted newest to
# oldest by last modification time.
list=${tmp}/${PROG}.list

function gen_work_list() {
    SECONDS=0
    # Find all the links in all the ${ARCHIVE}/<controller>/${linksrc}
    # directories, emitting a list of their modification times, size in bytes,
    # and full paths of the file the link points to, and then sort them so
    # that we process the tar balls from newest to oldest.
    rm -f ${list}
    > ${list}.unsorted
    # First we find all the ${linksrc} directories
    for linksrc_dir in $(find ${ARCHIVE}/ -maxdepth 2 -type d -name ${linksrc}); do
        # Find all the links in a given ${linksrc} directory that are links to
        # actual files (bad links are not emitted!).  For now, if it's a
        # duplicate name, just punt and avoid producing an error.
        find -L ${linksrc_dir} -type f -name '*.tar.xz' ${lb_arg} ${ub_arg} -printf "%TY-%Tm-%TdT%TT %s %p\n" 2>/dev/null >> ${list}.unsorted
        if [[ ${lowerbound} == 0 ]]; then
            # Find all the links in the same ${linksrc} directory that don't
            # link to anything so that we can count them as errors below.
            find -L $linksrc_dir -type l -name '*.tar.xz' -printf "%TY-%Tm-%TdT%TT %s %p\n" 2>/dev/null >> ${list}.unsorted
        fi
    done
    sort -k 1 -r ${list}.unsorted > ${list}
    rm -f ${list}.unsorted
    # Pad by one minute, the default smallest cronjob interval.
    let max_seconds=${SECONDS}+60
    return $(( ${max_seconds} * 2 ))
}

function move_symlink() {
    local hostname="${1}"
    local resultname="${2}"
    local linksrc="${3}"
    local linkdest="${4}"
    mv ${ARCHIVE}/${hostname}/${linksrc}/${resultname}.tar.xz ${ARCHIVE}/${hostname}/${linkdest}/${resultname}.tar.xz
    local status=${?}
    if [[ ${status} -ne 0 ]]; then
        log_error "${TS}: Cannot move symlink ${ARCHIVE}/${hostname}/${resultname}.tar.xz from ${linksrc} to ${linkdest}: code ${status}"
    fi
    return ${status}
}

function do_work() {
    SECONDS=0
    local status=0
    local max_seconds=${1}
    while read date size result; do
        (( ntotal++ ))

        resultname=$(basename ${result})
        resultname=${resultname%.tar.xz}

        link=$(readlink -e ${result})
        if [[ -z "${link}" ]]; then
            (( nerrs++ ))
            log_error "${TS}: symlink target for ${result} does not exist"
            hostname=$(basename $(dirname $(dirname ${result})))
            mkdir -p ${ARCHIVE}/${hostname}/${linkerr}
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for symlink"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        pbench-check-tb-age ${link}
        local status=${?}
        if [[ ${status} -gt 0 ]]; then
            (( nwarn++ ))
            log_warn "${TS}: ${result} is older than the configured maximum age (status = ${status})"
            hostname=$(basename $(dirname $(dirname ${result})))
            mkdir -p ${ARCHIVE}/${hostname}/${linkerr}
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for symlink"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        basedir=$(dirname ${link})
        hostname=$(basename ${basedir})

        # Make sure that all the relevant state directories exist
        mk_dirs ${hostname}
        status=${?}
        if [[ ${?} -ne 0 ]]; then
            (( nerrs++ ))
            log_error "${TS}: Creation of ${hostname} processing directories failed for ${result}: code ${status}"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        incoming=${INCOMING}/${hostname}/${resultname}
        if [[ -e ${incoming} ]]; then
            (( nerrs++ ))
            log_error "${TS}: Incoming result, ${incoming}, already exists, skipping ${result}"
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for already unpacked"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        mkdir -p ${incoming}.unpack
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            (( nerrs++ ))
            log_error "${TS}: 'mkdir ${incoming}.unpack' failed for ${result}: code ${status}"
            popd > /dev/null 2>&1
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi
        let start_time=$(timestamp-seconds-since-epoch)
        tar --extract --no-same-owner --touch --delay-directory-restore --file="${result}" --force-local --directory="${incoming}.unpack"
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            (( nerrs++ ))
            log_error "${TS}: 'tar -xf ${result}' failed: code ${status}"
            rm -rf ${incoming}.unpack
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed untar"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        # chmod directories to at least 555
        find ${incoming}.unpack/${resultname} -type d -print0 | xargs -0 chmod ugo+rx
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            (( nerrs++ ))
            log_error "${TS}: 'chmod ugo+rx' of subdirs ${resultname} for ${result} failed: code ${status}"
            rm -rf ${incoming}.unpack
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed find/chmod"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        # chmod files to at least 444
        chmod -R ugo+r ${incoming}.unpack/${resultname}
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            (( nerrs++ ))
            log_error "${TS}: 'chmod -R ugo+r ${resultname}' for ${result} failed: code ${status}"
            rm -rf ${incoming}.unpack
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed chmod"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        # Move the final unpacked tar ball into place
        mv ${incoming}.unpack/${resultname} ${INCOMING}/${hostname}/
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            (( nerrs++ ))
            log_error "${TS}: '${result}' does not contain ${resultname} directory at the top level; skipping"
            rm -rf ${incoming}.unpack
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed mv"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi
        rmdir ${incoming}.unpack
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            (( nwarn++ ))
            log_warn "${TS}: WARNING - '${result}' should only contain the ${resultname} directory at the top level, ignoring other content"
            rm -rf ${incoming}.unpack
        fi

        # Version 002 agents use the metadata log to store a prefix.
        # They may also store a user option in the metadata log.
        # We check for both of these here (n.b. if nothing is found
        # they are going to be empty strings):
        prefix=$(pbench-server-config -C ${INCOMING}/${hostname}/${resultname}/metadata.log prefix run)
        user=$(pbench-server-config -C ${INCOMING}/${hostname}/${resultname}/metadata.log user run)

        # if non-empty and does not contain a trailing slash, add one
        if [[ ! -z "${prefix}" && "${prefix%/}" = "${prefix}" ]]; then
            prefix=${prefix}/
        fi

        mkdir -p ${RESULTS}/${hostname}/${prefix}
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            (( nerrs++ ))
            log_error "${TS}: mkdir -p ${RESULTS}/${hostname}/${prefix} for ${result} failed: code ${status}"
            rm -rf ${incoming}
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed mkdir results prefix"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi
        # make a link in results/
        log_debug "ln -s ${incoming} ${RESULTS}/${hostname}/${prefix}${resultname}"
        ln -s ${incoming} ${RESULTS}/${hostname}/${prefix}${resultname}
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            (( nerrs++ ))
            log_error "${TS}: ln -s ${incoming} ${RESULTS}/${hostname}/${prefix}${resultname} for ${result} failed: code ${status}"
            rm -rf ${incoming}
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed ln results prefix"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        if [[ ! -z ${user} ]]; then
            # make a link in users/ but first make sure the directory exists
            mkdir -p ${USERS}/${user}/${hostname}/${prefix}
            status=${?}
            if [[ ${status} -ne 0 ]]; then
                (( nerrs++ ))
                log_error "${TS}: mkdir -p ${USERS}/${user}/${hostname}/${prefix} for ${result} failed: code ${status}"
                rm -rf ${incoming}
                rm -f ${RESULTS}/${hostname}/${prefix}${resultname}
                move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed mkdir users prefix"
                if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
                continue
            fi

            log_debug "ln -s ${incoming} ${USERS}/${user}/${hostname}/${prefix}${resultname}"
            ln -s ${incoming} ${USERS}/${user}/${hostname}/${prefix}${resultname}
            status=${?}
            if [[ ${status} -ne 0 ]]; then
                (( nerrs++ ))
                log_error "${TS}: code ${status}: ln -s ${incoming} ${USERS}/${user}/${hostname}/${prefix}${resultname}"
                rm -rf ${incoming}
                rm -f ${RESULTS}/${hostname}/${prefix}${resultname}
                move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed ln users prefix"
                if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
                continue
            fi
        fi

        move_symlink ${hostname} ${resultname} ${linksrc} ${linkdest}
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            (( nerrs++ ))
            # Cleanup needed here but trap takes care of it.
            rm -rf ${incoming}
            rm -f ${RESULTS}/${hostname}/${prefix}${resultname}
            rm -f ${USERS}/${user}/${hostname}/${prefix}${resultname}
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed move_symlink"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        let end_time=$(timestamp-seconds-since-epoch)
        let duration=end_time-start_time
        # log the success
        log_debug "${TS}: ${hostname}/${resultname}: success - elapsed time (secs): ${duration} - size (bytes): ${size}"
        (( ntbs++ ))

        # The job currently default to running once a minute, but once unpack
        # tar balls starts running, we want to re-check for new tar balls that
        # might have arrived while we were unpacking.  Once we spend time in
        # the loop for more than 2 times the max(1 minute, "time it takes to
        # make list of tar balls"), we'll break and exit to recalculate the
        # list.
        if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
    done
}

typeset -i ntbs=0
typeset -i ntotal=0
typeset -i nerrs=0
typeset -i nwarn=0
typeset -i nloops=0

while true; do
    gen_work_list
    max_seconds=${?}
    if [[ ! -s ${list} ]]; then
        break
    fi
    do_work ${max_seconds} < ${list}
    (( nloops++ ))
done

end_ts=$(timestamp)

if [[ ${ntotal} -gt 0 ]]; then
    (( nloops-- ))
    summary_text="(${PBENCH_ENV}) Processed ${ntotal} result tar balls, ${ntbs} successfully, with ${nloops} rechecks, ${nwarn} warnings, and ${nerrs} errors"
    printf -v summary_inner_json \
        "{\"%s\": \"%s\", \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": \"%s\", \"%s\": \"%s\", \"%s\": \"%s\"}" \
        "end_ts" "${end_ts}" \
        "errors" "${nerrs}" \
        "nrechecks" "${nloops}" \
        "ntbs" "${ntbs}" \
        "ntotal" "${ntotal}" \
        "nwarn" "${nwarn}" \
        "prog" "${PROG}" \
        "start_ts" "${start_ts}" \
        "text" "${summary_text}"
    printf -v summary_json "{\"pbench\": {\"report\": {\"summary\": %s}}}" "${summary_inner_json}"

    log_info "@cee:${summary_json}"
fi

log_finish

exit 0
