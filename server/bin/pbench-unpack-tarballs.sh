#! /bin/bash
# -*- mode: shell-script -*-

# This script is the first part of the pipeline that processes pbench
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
# - this script runs as a cron job
# - tarballs and md5 sums are uploaded by move/copy-results to
#   $ARCHIVE/$(hostname -s) area.
# - move/copy-results also makes a symlink to each tarball it uploads
#   in $ARCHIVE/TODO.

# This script loops over the contents of $archive/TODO, verifies the md5
# sum of each tarball, and if correct, it unpacks the tarball into
# .../incoming/$(hostname -s)/.  If everything works, it then moves the
# symlink from $ARCHIVE/TODO to $ARCHIVE/TO-COPY-SOS.


# load common things
. ${dir}/pbench-base.sh

# check that all the directories exist
test -d ${ARCHIVE} || doexit "Bad ARCHIVE=${ARCHIVE}"
test -d ${INCOMING} || doexit "Bad INCOMING=${INCOMING}"
test -d ${RESULTS} || doexit "Bad RESULTS=${RESULTS}"
test -d ${USERS} || doexit "Bad USERS=${USERS}"

# The link source and destination(s) for this script.
linksrc=TO-UNPACK
linkdest=UNPACKED
linkerr=WONT-UNPACK
linkdestlist=$(getconf.py -l unpacked-states pbench-server)

BUCKET="${1}"
if [[ -z "${BUCKET}" ]]; then
    lb_arg=""
    ub_arg=""
    lowerbound=0
    upperbound=""
    export PROG="${PROG}"
else
    lowerbound=$(getconf.py lowerbound pbench-unpack-tarballs/${BUCKET})
    if [[ -z "${lowerbound}" ]]; then
        lb_arg=""
        lowerbound=0
    else
        # Convert megabytes to bytes
        lowerbound=$(( ${lowerbound} * 1024 * 1024 ))
        lb_arg="-size +$(( ${lowerbound} - 1 ))c"
    fi
    upperbound=$(getconf.py upperbound pbench-unpack-tarballs/${BUCKET})
    if [[ -z "${upperbound}" ]]; then
        ub_arg=""
    else
        # Convert megabytes to bytes
        upperbound=$(( ${upperbound} * 1024 * 1024 ))
        ub_arg="-size -$(( ${upperbound} ))c"
    fi
    # We rename the PROG to include the bucket since we don't want to conflict
    # with other unpack tar balls running using different buckets at the same
    # time.
    export PROG="${PROG}-${BUCKET}"
fi

tmp=${TMP}/${PROG}.${$}
trap 'rm -rf ${tmp}' EXIT INT QUIT

mkdir -p ${tmp} || doexit "Failed to create ${tmp}"

log_init ${PROG}

log_info "${TS}"

# Accumulate errors and logs in files for reporting at the end.
mail_content=${tmp}/mail_content.log
> ${mail_content}
index_content=${tmp}/index_mail_contents
> ${index_content}

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
        find -L ${linksrc_dir} -type f -name '*.tar.xz' ! -name 'DUPLICATE__NAME*' ${lb_arg} ${ub_arg} -printf "%TY-%Tm-%TdT%TT %s %p\n" 2>/dev/null >> ${list}.unsorted
        if [[ ${lowerbound} == 0 ]]; then
            # Find all the links in the same ${linksrc} directory that don't
            # link to anything so that we can count them as errors below.
            find -L $linksrc_dir -type l -name '*.tar.xz' ! -name 'DUPLICATE__NAME*' -printf "%TY-%Tm-%TdT%TT %s %p\n" 2>/dev/null >> ${list}.unsorted
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
        log_error "${TS}: Cannot move symlink ${ARCHIVE}/${hostname}/${resultname}.tar.xz from ${linksrc} to ${linkdest}: code ${status}" "${mail_content}"
    fi
    return ${status}
}

function do_work() {
    SECONDS=0
    local status=0
    local max_seconds=${1}
    while read date size result; do
        ntotal=${ntotal}+1

        resultname=$(basename ${result})
        resultname=${resultname%.tar.xz}

        link=$(readlink -e ${result})
        if [[ -z "${link}" ]]; then
            log_error "${TS}: symlink target for ${result} does not exist" "${mail_content}"
            nerrs=${nerrs}+1
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
            log_error "${TS}: Creation of ${hostname} processing directories failed for ${result}: code ${status}" "${mail_content}"
            nerrs=${nerrs}+1
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        incoming=${INCOMING}/${hostname}/${resultname}
        if [[ -e ${incoming} ]]; then
            log_error "${TS}: Incoming result, ${incoming}, already exists, skipping ${result}" "${mail_content}"
            nerrs=${nerrs}+1
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for already unpacked"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        mkdir -p ${incoming}.unpack
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            log_error "${TS}: 'mkdir ${incoming}.unpack' failed for ${result}: code ${status}" "${mail_content}"
            nerrs=${nerrs}+1
            popd > /dev/null 2>&1
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi
        let start_time=$(timestamp-seconds-since-epoch)
        tar --extract --no-same-owner --touch --delay-directory-restore --file="${result}" --force-local --directory="${incoming}.unpack"
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            log_error "${TS}: 'tar -xf ${result}' failed: code ${status}" "${mail_content}"
            rm -rf ${incoming}.unpack
            nerrs=${nerrs}+1
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed untar"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        # chmod directories to at least 555
        find ${incoming}.unpack/${resultname} -type d -print0 | xargs -0 chmod ugo+rx
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            log_error "${TS}: 'chmod ugo+rx' of subdirs ${resultname} for ${result} failed: code ${status}" "${mail_content}"
            nerrs=${nerrs}+1
            rm -rf ${incoming}.unpack
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed find/chmod"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        # chmod files to at least 444
        chmod -R ugo+r ${incoming}.unpack/${resultname}
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            log_error "${TS}: 'chmod -R ugo+r ${resultname}' for ${result} failed: code ${status}" "${mail_content}"
            nerrs=${nerrs}+1
            rm -rf ${incoming}.unpack
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed chmod"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        # Move the final unpacked tar ball into place
        mv ${incoming}.unpack/${resultname} ${INCOMING}/${hostname}/
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            log_error "${TS}: '${result}' does not contain ${resultname} directory at the top level; skipping" "${mail_content}"
            rm -rf ${incoming}.unpack
            nerrs=${nerrs}+1
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed mv"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi
        rmdir ${incoming}.unpack
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            log_error "${TS}: WARNING - '${result}' should only contain the ${resultname} directory at the top level, ignoring other content" "${mail_content}"
            rm -rf ${incoming}.unpack
            nwarn=${nwarn}+1
        fi

        # Version 002 agents use the metadata log to store a prefix.
        # They may also store a user option in the metadata log.
        # We check for both of these here (n.b. if nothing is found
        # they are going to be empty strings):
        prefix=$(getconf.py -C ${INCOMING}/${hostname}/${resultname}/metadata.log prefix run)
        user=$(getconf.py -C ${INCOMING}/${hostname}/${resultname}/metadata.log user run)

        # Version 001 agents use a prefix file.  If there is a prefix file,
        # create a link as specified in the prefix file.  pbench-dispatch
        # has already moved it to the .prefix subdir
        prefixfile=${basedir}/.prefix/${resultname}.prefix
        if [[ -f ${prefixfile} ]]; then
            prefix=$(cat ${prefixfile})
        fi

        # if non-empty and does not contain a trailing slash, add one
        if [[ ! -z "${prefix}" && "${prefix%/}" = "${prefix}" ]]; then
            prefix=${prefix}/
        fi

        mkdir -p ${RESULTS}/${hostname}/${prefix}
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            log_error "${TS}: mkdir -p ${RESULTS}/${hostname}/${prefix} for ${result} failed: code ${status}" "${mail_content}"
            rm -rf ${incoming}
            nerrs=${nerrs}+1
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed mkdir results prefix"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi
        # make a link in results/
        log_info "ln -s ${incoming} ${RESULTS}/${hostname}/${prefix}${resultname}"
        ln -s ${incoming} ${RESULTS}/${hostname}/${prefix}${resultname}
        status=${?}
        if [[ ${status} -ne 0 ]]; then
            log_error "${TS}: ln -s ${incoming} ${RESULTS}/${hostname}/${prefix}${resultname} for ${result} failed: code ${status}" "${mail_content}"
            nerrs=${nerrs}+1
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
                log_error "${TS}: mkdir -p ${USERS}/${user}/${hostname}/${prefix} for ${result} failed: code ${status}" "${mail_content}"
                rm -rf ${incoming}
                rm -f ${RESULTS}/${hostname}/${prefix}${resultname}
                nerrs=${nerrs}+1
                move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed mkdir users prefix"
                if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
                continue
            fi

            log_info "ln -s ${incoming} ${USERS}/${user}/${hostname}/${prefix}${resultname}"
            ln -s ${incoming} ${USERS}/${user}/${hostname}/${prefix}${resultname}
            status=${?}

            if [[ ${status} -ne 0 ]]; then
                log_error "${TS}: code ${status}: ln -s ${incoming} ${USERS}/${user}/${hostname}/${prefix}${resultname}" "${mail_content}"
                nerrs=${nerrs}+1
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
            nerrs=${nerrs}+1
            # Cleanup needed here but trap takes care of it.
            rm -rf ${incoming}
            rm -f ${RESULTS}/${hostname}/${prefix}${resultname}
            rm -f ${USERS}/${user}/${hostname}/${prefix}${resultname}
            move_symlink ${hostname} ${resultname} ${linksrc} ${linkerr} || doexit "Error handling failed for failed move_symlink"
            if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
            continue
        fi

        # Create a link in each state dir - if any fail, we should delete them all? No, that
        # would be racy.
        let toterr=0
        let totsuc=0
        for state in ${linkdestlist}; do
            ln -sf ${ARCHIVE}/${hostname}/${resultname}.tar.xz ${ARCHIVE}/${hostname}/${state}/${resultname}.tar.xz
            status=${?}
            if [[ ${status} -eq 0 ]]; then
                let totsuc+=1
            else
                log_error "${TS}: Cannot create ${ARCHIVE}/${hostname}/${resultname}.tar.xz link in state ${state}: code ${status}" "${mail_content}"
                let toterr+=1
            fi
        done
        if [[ ${toterr} -gt 0 ]]; then
            # Count N link creations as one error since it is for handling of a
            # single tarball.
            let nerrs+=1
        fi

        let end_time=$(timestamp-seconds-since-epoch)
        let duration=end_time-start_time
        # log the success
        log_info "${TS}: ${hostname}/${resultname}: success - elapsed time (secs): ${duration} - size (bytes): ${size}"
        ntb=${ntb}+1

        # The job currently default to running once a minute, but once unpack
        # tar balls starts running, we want to re-check for new tar balls that
        # might have arrived while we were unpacking.  Once we spend time in
        # the loop for more than 2 times the max(1 minute, "time it takes to
        # make list of tar balls"), we'll break and exit to recalculate the
        # list.
        if [[ ${SECONDS} -ge ${max_seconds} ]]; then break; fi
    done
}

typeset -i ntb=0
typeset -i ntotal=0
typeset -i nerrs=0
typeset -i ndups=0
typeset -i nwarn=0

while true; do
    gen_work_list
    max_seconds=${?}
    if [[ ! -s ${list} ]]; then
        break
    fi
    do_work ${max_seconds} < ${list}
done

log_info "${TS}: Processed ${ntb} tarballs"

log_finish

subj="${PROG}.${TS}(${PBENCH_ENV}) - w/ ${nerrs} errors"
cat << EOF > ${index_content}
${subj}
Processed ${ntotal} result tar balls, ${ntb} successfully, ${nwarn} warnings, ${nerrs} errors, and ${ndups} duplicates

EOF
cat ${mail_content} >> ${index_content}
pbench-report-status --name ${PROG} --pid ${$} --timestamp $(timestamp) --type status ${index_content}

exit 0
