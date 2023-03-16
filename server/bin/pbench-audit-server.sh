#! /bin/bash
#
# Audit the fs-version-001 incoming, results, and users directory structures.
#
# NOTE: This is a pure audit, no changes to any of the hierarchies
# are made by this script.

# Approach:
#   Review the incoming hierarchy (verify_controllers $INCOMING)
#     Find "bad" controllers (not a sub-directory of $INCOMING)
#     For each "good" controller do:
#       Identify empty controllers
#       Identify controllers that contain files and not directories or links
#       Review each unpacked tar ball hierarchy or unpack link
#         Flag empty tar ball directories
#         Flag invalid tar ball links
#         Flag tar ball links pointing to an invalid unpack directory
#   Review the results hierarchy (verify_controllers $RESULTS)
#     Find "bad" controllers (not a sub-directory of $RESULTS)
#     For each "good" controller do:
#       Identify empty controllers
#       Identify controllers that contain files and not directories or links
#         Tar ball links that don't point to $INCOMING
#         Tar ball links that exist in a prefix hierarchy but don't have a
#           prefix file
#         Tar ball links that exist in a prefix hierarchy but have an invalid
#           prefix file (can't read it)
#         Tar ball links that exist in a prefix hierarchy but don't match the
#           stored prefix file prefix
#   Review the users hierarchy (verify_users)
#     Find "bad" users (not a sub-directory of $USERS)
#     For each "good" user do:
#       Review it just like a results hierarchy
#         (verify_controllers $USER/<user>)

# load common things
. $dir/pbench-base.sh

test -d "${INCOMING}" || doexit "Bad INCOMING=${INCOMING}"
test -d "${RESULTS}"  || doexit "Bad RESULTS=${RESULTS}"
test -d "${USERS}"    || doexit "Bad USERS=${USERS}"

# Work files
workdir=$TMP/$PROG.work.$$
report=$workdir/report
incoming_report=$workdir/incoming_report
results_report=$workdir/results_report
users_report=$workdir/users_report
bad_controllers=$workdir/badcontrollers
controllers=$workdir/controllers
non_prefixes=$workdir/nonprefixes
wrong_prefixes=$workdir/wrongprefixes
unexpected_symlinks=$workdir/unexpectedsymlinks
unexpected_files=$workdir/unexpectedfiles
unexpected_objects=$workdir/unexpectedobjects
directories=$workdir/directories
tarballs=$workdir/tarballs
linkdirs=$workdir/linkdirs
empty=$workdir/empty
users=$workdir/users

log_init ${PROG}

# Make sure the directory exists
mkdir -p ${workdir}
if [[ ! -d "${workdir}" ]]; then
    log_exit "${TS}: failed to create working directory, ${workdir}" 2
fi

trap "rm -rf $workdir" EXIT INT QUIT

function verify_incoming {
    controllers_arg=${1}

    local let cnt=0

    while read controller ;do
        lclreport="${workdir}/$(basename -- ${controller})"
        > ${lclreport}

        empty_tarball_dirs="${workdir}/emptytarballdirs"
        > ${empty_tarball_dirs}
        unpacking_tarball_dirs="${workdir}/unpackingtarballdirs"
        > ${unpacking_tarball_dirs}
        tarball_links="${workdir}/tarballlinks"
        > ${tarball_links}
        find $INCOMING/${controller} -maxdepth 1 \
                   \( -type d ! -name ${controller} ! -name '*.unpack'   -empty -fprintf ${empty_tarball_dirs} "\t\t%f\n" \) \
                -o \( -type d ! -name ${controller}   -name '*.unpack'          -fprintf ${unpacking_tarball_dirs} "\t\t%f\n" \) \
                -o \( -type l                                                   -fprintf ${tarball_links} "\t\t%f\n" \)
        status=$?
        if [[ $status -ne 0 ]]; then
            printf "*** ERROR *** unable to traverse ${INCOMING}/${controller}: find failed with ${status}"
            let cnt=cnt+1
            continue
        fi

        if [[ -s ${empty_tarball_dirs} ]]; then
            printf "\tEmpty tar ball directories:\n" >> ${lclreport}
            sort ${empty_tarball_dirs} >> ${lclreport} 2>&1
        fi
        rm ${empty_tarball_dirs}

        invalid_unpacking_dirs="${workdir}/invalidunpacking"
        while read tb_u ; do
            tb=${tb_u%*.unpack}
            if [[ -r ${unpack_dir}/${controller}/${tb}.tar.xz || -r ${re_unpack_dir}/${controller}/${tb}.tar.xz ]]; then
                continue
            fi
            printf "\t\t${tb_u}\n"
        done < ${unpacking_tarball_dirs} > ${invalid_unpacking_dirs}
        rm ${unpacking_tarball_dirs}

        if [[ -s ${invalid_unpacking_dirs} ]]; then
            printf "\tInvalid unpacking directories (missing tar ball):\n" >> ${lclreport}
            sort ${invalid_unpacking_dirs} >> ${lclreport} 2>&1
        fi
        rm ${invalid_unpacking_dirs}

        if [[ -s ${tarball_links} ]]; then
            printf "\tInvalid tar ball links:\n" >> ${lclreport}
            sort ${tarball_links} >> ${lclreport} 2>&1
        fi
        rm ${tarball_links}

        if [[ -s ${lclreport} ]]; then
            printf "\nIncoming issues for controller: ${controller}\n"
            cat ${lclreport}
            let cnt=cnt+1
        fi
        rm ${lclreport}
    done < ${controllers_arg}

    return $cnt
}

function verify_results {
    controllers_arg=${1}
    user_arg=${2}

    if [[ -z ${user_arg} ]]; then
        results_hierarchy=$RESULTS
    else
        results_hierarchy=$USERS/${user_arg}
    fi

    local let cnt=0

    while read controller ;do
        lclreport="${workdir}/$(basename -- ${controller})"
        > ${lclreport}

        # The hierarchy of a controller in the results tree should only
        # contain directories and symlinks, where symlinks could be anywhere
        # in the hierarchy of directories, as long as the path from the
        # controller directory to the symlink is defined by a prefix file. If
        # no prefix file exists, then the default of a symlink in the
        # controller is all that should exist for a given tar ball.
        empty_tarball_dirs="${workdir}/emptytarballdirs"
        > ${empty_tarball_dirs}
        tarball_links="${workdir}/tarballlinks"
        > ${tarball_links}.unsorted
        find ${results_hierarchy}/${controller} \
                \( -type d ! -name ${controller} -empty -fprintf ${empty_tarball_dirs} "\t\t%P\n" \) \
                -o \( -type l -fprintf ${tarball_links}.unsorted "%P %l\n" \)
        status=$?
        if [[ $status -ne 0 ]]; then
            printf "*** ERROR *** unable to traverse ${results_hierarchy}/${controller}: find failed with $status" >> ${lclreport}
            let cnt=cnt+1
        fi

        if [[ -s ${empty_tarball_dirs} ]]; then
            printf "\tEmpty tar ball directories:\n" >> ${lclreport}
            sort ${empty_tarball_dirs} >> ${lclreport} 2>&1
        fi
        rm ${empty_tarball_dirs}

        # Verify the link name should be a link to the $INCOMING directory or
        # a symlink of the same name, and should be the name of a valid tar
        # ball.
        incorrect_tb_dir_links="${workdir}/incorrecttbdirlinks"
        > ${incorrect_tb_dir_links}
        invalid_tb_dir_links="${workdir}/invalidtbdirlinks"
        > ${invalid_tb_dir_links}
        bad_prefixes="${workdir}/badprefixes"
        > ${bad_prefixes}
        unexpected_user_links="${workdir}/unexpecteduserlinks"
        > ${unexpected_user_links}
        wrong_user_links="${workdir}/wronguserlinks"
        > ${wrong_user_links}
        sort ${tarball_links}.unsorted > ${tarball_links}
        rm ${tarball_links}.unsorted
        while read path link ; do
            tb=$(basename -- ${path})
            if [[ "${link}" != "$INCOMING/${controller}/${tb}" ]]; then
                # The link is not constructed to point to the proper
                # location in the incoming hierarchy.
                printf "\t\t${path}\n" >> ${incorrect_tb_dir_links}
            elif [[ ! -d $INCOMING/${controller}/${tb} && ! -L $INCOMING/${controller}/${tb} ]]; then
                # The link in the results directory does not point to
                # a directory or link in the incoming hierarchy.
                printf "\t\t${path}\n" >> ${invalid_tb_dir_links}
            else
                prefix_path=$(dirname -- ${path})
                # Version 002 agents use the metadata log to store a
                # prefix.
                __prefix=$(pbench-server-config -C $INCOMING/${controller}/${tb}/metadata.log prefix run)
                _prefix=${__prefix#/}
                prefix=${_prefix%/}
                if [[ "${prefix_path}" == "." ]]; then
                    # No prefix, ensure it doesn't have a prefix in the
                    # metadata.log file.
                    if [[ ! -z "${prefix}" ]]; then
                        # The stored prefix does not match the
                        # actual prefix
                        printf "\t\t${path}\n" >> ${bad_prefixes}
                    fi
                else
                    # Have a prefix ...
                    if [[ ! -z "${prefix}" ]]; then
                        # Have a prefix in the metadata.log file ...
                        if [[ ${prefix} != ${prefix_path} ]]; then
                            # The stored prefix does not match the
                            # actual prefix
                            printf "\t\t${path}\n" >> ${bad_prefixes}
                        fi
                    else
                        # We have a prefix on-disk but no prefix in the metadata
                        printf "\t\t${path}\n" >> ${bad_prefixes}
                    fi
                fi
                if [[ ! -z "${user_arg}" ]]; then
                    # We are reviewing a user tree, so check the user in
                    # the configuration.  Version 002 agents use the
                    # metadata log to store a user as well.
                    user=$(pbench-server-config -C $INCOMING/${controller}/${tb}/metadata.log user run)
                    if [[ -z "${user}" ]]; then
                        # No user in the metadata.log of the tar ball, but
                        # we are examining a link in the user tree that
                        # does not have a configured user, report it.
                        printf "\t\t${path}\n" >> ${unexpected_user_links}
                    elif [[ "${user_arg}" != "${user}" ]]; then
                        # Configured user does not match the user tree in
                        # which we found the link.
                        printf "\t\t${path}\n" >> ${wrong_user_links}
                    fi
                fi
            fi
        done < ${tarball_links}
        rm ${tarball_links}

        if [[ -s ${incorrect_tb_dir_links} ]]; then
            printf "\tIncorrectly constructed tar ball links:\n" >> ${lclreport}
            cat ${incorrect_tb_dir_links} >> ${lclreport}
        fi
        rm ${incorrect_tb_dir_links}

        if [[ -s ${invalid_tb_dir_links} ]]; then
            printf "\tTar ball links to invalid incoming location:\n" >> ${lclreport}
            cat ${invalid_tb_dir_links} >> ${lclreport}
        fi
        rm ${invalid_tb_dir_links}

        if [[ -s ${bad_prefixes} ]]; then
            printf "\tTar ball links with bad prefixes:\n" >> ${lclreport}
            cat ${bad_prefixes} >> ${lclreport}
        fi
        rm ${bad_prefixes}

        if [[ -s ${unexpected_user_links} ]]; then
            printf "\tTar ball links not configured for this user:\n" >> ${lclreport}
            cat ${unexpected_user_links} >> ${lclreport}
        fi
        rm ${unexpected_user_links}

        if [[ -s ${wrong_user_links} ]]; then
            printf "\tTar ball links for the wrong user:\n" >> ${lclreport}
            cat ${wrong_user_links} >> ${lclreport}
        fi
        rm ${wrong_user_links}

        if [[ -s ${lclreport} ]]; then
            if [[ ! -z "${user_arg}" ]]; then
                printf "\nResults issues for controller: ${user_arg}/${controller}\n"
            else
                printf "\nResults issues for controller: ${controller}\n"
            fi
            cat ${lclreport}
            let cnt=cnt+1
        fi
        rm ${lclreport}
    done < ${controllers_arg}
    return $cnt
}

function verify_controllers {
    # Assert that $1/ only contains controller directories/
    hierarchy_root=${1}

    if [[ "${hierarchy_root}" = "$INCOMING" ]]; then
        kind="incoming"
        user=""
    elif [[ "${hierarchy_root}" = "$RESULTS" ]]; then
        kind="results"
        user=""
    elif [[ "$(dirname -- ${hierarchy_root})" = "$USERS" ]]; then
        kind="results"
        user=$(basename -- ${hierarchy_root})
    else
        printf "${PROG}: verify_controllers bad argument, hierarchy_root=\"${hierarchy_root}\"\n" >&2
        return 1
    fi

    local let cnt=0

    # Find all the normal controller directories, ignoring the "." (current)
    # directory (if the $hierarchy_root directory resolves to "."), and
    # ignoring the $hierarchy_root directory itself, while keeping them all
    # in sorted order.
    > ${unexpected_objects}
    > ${controllers}.unsorted
    find ${hierarchy_root} -maxdepth 1 \
            \( ! -type d -fprintf ${unexpected_objects} "\t%f\n" \) \
            -o \( -type d ! -name . ! -name $(basename -- ${hierarchy_root}) -fprintf ${controllers}.unsorted "%f\n" \)
    status=$?
    if [[ $status -ne 0 ]]; then
        printf "*** ERROR *** unable to traverse hiearchy ${hierarchy_root}: find failed with $status\n"
        let cnt=cnt+1
    fi

    if [[ -s ${unexpected_objects} ]]; then
        printf "\nUnexpected files found:\n"
        sort ${unexpected_objects} 2>&1
        let cnt=cnt+1
    fi
    rm -f ${unexpected_objects}

    sort ${controllers}.unsorted > ${controllers}
    if [[ -s ${controllers} ]]; then
        emptylist="${workdir}/empty_controllers"
        > ${emptylist}
        unexpectedlist="${workdir}/controllers_w_unexpected"
        > ${unexpectedlist}
        verifylist="${workdir}/controllers_to_verify"
        > ${verifylist}
        while read controller ;do
            # Report any controllers with objects other than directories
            # and links, while also recording any empty controllers.
            > ${unexpected_objects}
            > ${empty}
            find ${hierarchy_root}/${controller} -maxdepth 1 \
                    \( ! -type d ! -type l -fprintf ${unexpected_objects} "%f\n" \) \
                    -o \( -type d -name ${controller} -empty -fprintf ${empty} "%f\n" \)
            status=$?
            if [[ $status -ne 0 ]]; then
                printf "*** ERROR *** unable to traverse hiearchy ${hierarchy_root}/${controller}: find failed with $status\n"
                let cnt=cnt+1
            fi
            if [[ -s "${empty}" ]]; then
                printf "\t${controller}\n" >> ${emptylist}
            elif [[ -s "${unexpected_objects}" ]]; then
                printf "\t${controller}\n" >> ${unexpectedlist}
                printf "\t${controller}\n" >> ${verifylist}
            else
                printf "\t${controller}\n" >> ${verifylist}
            fi
            rm -f ${unexpected_objects} ${empty}
        done < ${controllers}

        if [[ -s "${emptylist}" ]]; then
            printf "\nControllers which are empty:\n"
            cat ${emptylist}
            let cnt=cnt+1
        fi
        rm -f ${emptylist}
        if [[ -s "${unexpectedlist}" ]]; then
            printf "\nControllers which have unexpected objects:\n"
            cat ${unexpectedlist}
            let cnt=cnt+1
        fi
        rm -f ${unexpectedlist}
        if [[ -s "${verifylist}" ]]; then
            verify_${kind} ${verifylist} ${user}
            if [[ $? -gt 0 ]]; then
                let cnt=cnt+1
            fi
        fi
        rm -f ${verifylist}
    fi
    rm -f ${controllers}.unsorted ${controllers}

    return $cnt
}

function verify_users {
    local let cnt=0

    # The $USERS hierarchy should only contain directories at the first
    # level, which themselves should be just like a sub-set of the
    # $RESULTS tree.
    > ${unexpected_objects}
    > ${users}.unsorted
    find $USERS -maxdepth 1 \
            \( ! -type d -fprintf ${unexpected_objects} "\t%f\n" \) \
            -o \( -type d ! -name . ! -name $(basename -- $USERS) -fprintf ${users}.unsorted "%f\n" \)
    status=$?
    if [[ $status -ne 0 ]]; then
        printf "*** ERROR *** unable to traverse hiearchy $USERS: find failed with $status\n"
        let cnt=cnt+1
    fi

    if [[ -s ${unexpected_objects} ]]; then
        printf "\nUnexpected files found:\n"
        sort ${unexpected_objects} 2>&1
        let cnt=cnt+1
    fi
    rm -f ${unexpected_objects}

    sort ${users}.unsorted > ${users}
    while read user ;do
        verify_controllers $USERS/${user}
        if [[ $? -gt 0 ]]; then
            let cnt=cnt+1
        fi
    done < ${users}
    rm -f ${users}.unsorted ${users}

    return $cnt
}

# Save the previous report.
latest_report=${LOGSDIR}/${PROG}/report.latest.txt
prev_report=${LOGSDIR}/${PROG}/report.prev.txt
mv ${latest_report} ${prev_report} 2>/dev/null
# Ensure we have an existing intermediate report file.
> ${report}

let ret=0

sTS=$(timestamp)
verify_controllers $INCOMING > ${incoming_report} 2>&1
if [[ $? -ne 0 ]]; then
    let ret=ret+1
fi
eTS=$(timestamp)
if [[ -s ${incoming_report} ]]; then
    printf "\n\nstart-${sTS}: incoming hierarchy: $INCOMING\n" >> ${report}
    cat ${incoming_report} >> ${report}
    printf "\nend-${eTS}: incoming hierarchy: $INCOMING\n" >> ${report}
fi

sTS=$(timestamp)
verify_controllers $RESULTS > ${results_report} 2>&1
if [[ $? -ne 0 ]]; then
    let ret=ret+1
fi
eTS=$(timestamp)
if [[ -s ${results_report} ]]; then
    printf "\n\nstart-${sTS}: results hierarchy: $RESULTS\n" >> ${report}
    cat ${results_report} >> ${report}
    printf "\nend-${eTS}: results hierarchy: $RESULTS\n" >> ${report}
fi

sTS=$(timestamp)
verify_users > ${users_report} 2>&1
if [[ $? -ne 0 ]]; then
    let ret=ret+1
fi
eTS=$(timestamp)
if [[ -s ${users_report} ]]; then
    printf "\n\nstart-${sTS}: users hierarchy: $USERS\n" >> ${report}
    cat ${users_report} >> ${report}
    printf "\nend-${eTS}: users hierarchy: $USERS\n" >> ${report}
fi

# Move the completed intermediate report to be the latest.
mv ${report} ${latest_report}
if [[ -s "${latest_report}" ]]; then
    log_error "${TS}(${PBENCH_ENV}) - audit found problems, please review ${latest_report}"
fi

log_finish

exit $ret
