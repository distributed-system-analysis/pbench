#! /bin/bash
# -*- mode: shell-script -*-

# This script is the first part of the pipeline that processes pbench results
# tar balls.

# `pbench-unpack-tarballs` looks for tar balls in the "unpack directory"
# hierarchy and unpacks any tar balls it finds.  An optional "bucket" argument
# can be given to only consider tar balls in a certain size range determined by
# the administrator.  It runs under cron once a minute in order to minimize the
# delay between uploading the results and making them available for viewing via
# the web server.

# This script loops over the contents of ${[re_]unpack_dir}/<controller>/ and
# and unpacks each tar ball into .../incoming/<controller>/, establishing the
# proper .../results and .../users symlinks to it.

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

# Load common things
. ${dir}/pbench-base.sh

if [[ "${PIPELINE}" == "re-unpack" ]]; then
    # The source for re-unpacking.
    unpack_dir=$(pbench-server-config pbench-re-unpack-dir pbench-server)
else
    # The source for normal flow of unpacking.
    unpack_dir=$(pbench-server-config pbench-unpack-dir pbench-server)
fi

# Check that all the required directories exist.
test -d "${unpack_dir}" || doexit "Bad unpack_dir=${unpack_dir}"
test -d "${INCOMING}"   || doexit "Bad INCOMING=${INCOMING}"
test -d "${RESULTS}"    || doexit "Bad RESULTS=${RESULTS}"
test -d "${USERS}"      || doexit "Bad USERS=${USERS}"

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
    # Find all the tar balls in all the ${unpack_dir}/<controller> directories,
    # emitting a list of their modification times, size in bytes, and full paths
    # of the files, and then sort them so that we process the tar balls from
    # newest to oldest.
    find ${unpack_dir} \
        -type f -name '*.tar.xz' ${lb_arg} ${ub_arg} \
        -printf "%TY-%Tm-%TdT%TT %s %p\n" 2>/dev/null | sort -k 1 -r > ${list}
    # Pad by one minute, the default smallest cronjob interval, and then double.
    return $(( (SECONDS+60)*2 ))
}

function delete_result() {
    rm ${1} ${1}.md5
    local status=${?}
    if [[ ${status} -ne 0 ]]; then
        log_error "${TS}: Cannot remove result tar ball ${1} from ${unpack_dir} hierarchy: code ${status}"
    fi
    return ${status}
}

function do_work() {
    local max_seconds=${1}
    local resultname
    local basedir
    local hostname
    local status
    SECONDS=0
    while read date size result; do
        (( ntotal++ ))

        resultname=$(basename ${result})
        resultname=${resultname%.tar.xz}

        pbench-check-tb-age ${result}
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            (( nold++ ))
            log_info "${TS}: ${result} is older than the configured maximum age (status = ${status})"
            delete_result ${result}
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        basedir=$(dirname ${result})
        hostname=$(basename ${basedir})

        incoming=${INCOMING}/${hostname}/${resultname}
        if [[ -e ${incoming} ]]; then
            (( nwarn++ ))
            log_warn "${TS}: Incoming result, ${incoming}, already exists, skipping ${result}"
            delete_result ${result}
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        mkdir -p ${incoming}.unpack
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            (( nerrs++ ))
            log_error "${TS}: 'mkdir ${incoming}.unpack' failed for ${result}: code ${status}"
            delete_result ${result}
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
            delete_result ${result}
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
            delete_result ${result}
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
            delete_result ${result}
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
            delete_result ${result}
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

        # At this point we can remove the result tar ball it is no longer
        # needed.
        delete_result ${result}

        # Version 002 agents use the metadata log to store a prefix.  They may
        # also store a user option in the metadata log.  We check for both of
        # these here (n.b. if nothing is found they are going to be empty
        # strings):
        prefix=$(pbench-server-config -C ${INCOMING}/${hostname}/${resultname}/metadata.log prefix run)
        user=$(pbench-server-config -C ${INCOMING}/${hostname}/${resultname}/metadata.log user run)

        # If non-empty and does not contain a trailing slash, add one
        if [[ ! -z "${prefix}" && "${prefix%/}" = "${prefix}" ]]; then
            prefix=${prefix}/
        fi

        mkdir -p ${RESULTS}/${hostname}/${prefix}
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            (( nerrs++ ))
            log_error "${TS}: mkdir -p ${RESULTS}/${hostname}/${prefix} for ${result} failed: code ${status}"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi
        # Make a link in results/
        ln -s ${incoming} ${RESULTS}/${hostname}/${prefix}${resultname}
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            (( nerrs++ ))
            log_error "${TS}: ln -s ${incoming} ${RESULTS}/${hostname}/${prefix}${resultname} for ${result} failed: code ${status}"
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
                if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
                continue
            fi

            ln -s ${incoming} ${USERS}/${user}/${hostname}/${prefix}${resultname}
            status=${?}
            if [[ ${status} -ne 0 ]]; then
                (( nerrs++ ))
                log_error "${TS}: code ${status}: ln -s ${incoming} ${USERS}/${user}/${hostname}/${prefix}${resultname}"
                if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
                continue
            fi
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
typeset -i nold=0
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
    summary_text="(${PBENCH_ENV}) Processed ${ntotal} result tar balls, ${ntbs}"
    summary_text+=" successfully, with ${nloops} rechecks, ${nold} too old to"
    summary_text+=" unpack, ${nwarn} warnings, and ${nerrs} errors"
    printf -v summary_inner_json \
        "{\"%s\": \"%s\", \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": \"%s\", \"%s\": \"%s\", \"%s\": \"%s\"}" \
        "end_ts" "${end_ts}" \
        "errors" "${nerrs}" \
        "nold" "${nold}" \
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
