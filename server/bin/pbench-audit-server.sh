#! /bin/bash

# Audit the fs-version-001 archive, incoming, results, and users
# directory structures.
#
# NOTE: This is a pure audit, no changes to any of the hierarchies
# are made by this script.

# Approach:
#   Review the archive hierarchy (verify_archive)
#     Find "bad" controllers (not a sub-directory of $ARCHIVE)
#     For each "good" controller do:
#       Verify all sub-directories of a given controller are one
#         of the expected state directories
#       Verify all files are *.tar.xz[.md5]
#         flagging *.tar.xz.prefix or prefix.*.tar.xz in the
#         controller directory
#       Verify all prefix files in .prefix directories are *.prefix
#   Review the incoming hierarchy (verify_controllers $INCOMING)
#     Find "bad" controllers (not a sub-directory of $INCOMING)
#     For each "good" controller do:
#       Identify controllers that don't have a $ARCHIVE directory
#       Identify empty controllers
#       Identify controllers that contain files and not directories or links
#       Review each unpacked tar ball hierarchy or unpack link
#         Flag expanded tar ball directories that don't exist in $ARCHIVE
#         Flag empty tar ball directories
#         Flag invalid tar ball links
#         Flag tar ball links pointing to an invalid unpack directory
#         Flag tar ball links/directories which don't have a tar ball
#           in the $ARCHIVE hierarchy
#   Review the results hierarchy (verify_controllers $RESULTS)
#     Find "bad" controllers (not a sub-directory of $RESULTS)
#     For each "good" controller do:
#       Identify controllers that don't have a $ARCHIVE directory
#       Identify empty controllers
#       Identify controllers that contain files and not directories or links
#         Tar ball links that don't point to $INCOMING
#         Tar ball links that don't ultimately have a tar ball in $ARCHIVE
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

test -d $ARCHIVE || doexit "Bad ARCHIVE=$ARCHIVE"
test -d $INCOMING || doexit "Bad INCOMING=$INCOMING"
test -d $RESULTS || doexit "Bad RESULTS=$RESULTS"
test -d $USERS || doexit "Bad USERS=$USERS"

# Work files
workdir=$TMP/$PROG.work.$$
report=$workdir/report
archive_report=$workdir/archive_report
incoming_report=$workdir/incoming_report
results_report=$workdir/results_report
users_report=$workdir/users_report
index_content=$workdir/index_content
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

# Make sure the directory exists
mkdir -p $workdir

trap "rm -rf $workdir" EXIT INT QUIT

for ldir in $LINKDIRS; do printf "\t  ${ldir}\n"; done | sort > ${linkdirs}

function verify_subdirs {
    directories_arg=${1}

    let cnt=0

    if [ -s ${directories_arg} ]; then
        grep -vE "(_QUARANTINED|WONT-INDEX)" ${directories_arg} > ${directories_arg}.linkdirs
        comm -13 ${linkdirs} ${directories_arg}.linkdirs > ${directories_arg}.unexpected
        if [ -s ${directories_arg}.unexpected ]; then
            printf "\t* Unexpected state directories found in this controller directory:\n"
            printf "\t  ++++++++++\n"
            cat ${directories_arg}.unexpected
            printf "\t  ----------\n"
            let cnt=cnt+1
        fi
    else
        printf "\t* No state directories found in this controller directory.\n"
        let cnt=cnt+1
    fi
    return $cnt
}

function verify_tarball_names {
    unexpected_symlinks_arg=${1}
    unexpected_objects_arg=${2}
    tarballs_arg=${3}

    let cnt=0

    if [ -s ${unexpected_symlinks_arg} ]; then
        printf "\t* Unexpected symlinks in controller directory:\n"
        printf "\t  ++++++++++\n"
        cat ${unexpected_symlinks_arg}
        printf "\t  ----------\n"
        let cnt=cnt+1
    fi

    if [ -s ${unexpected_objects_arg} ]; then
        printf "\t* Unexpected files in controller directory:\n"
        printf "\t  ++++++++++\n"
        cat ${unexpected_objects_arg}
        printf "\t  ----------\n"
        let cnt=cnt+1
    fi

    if [ ! -s ${tarballs_arg} ]; then
        printf "\t* No tar ball files found in this controller directory.\n"
        let cnt=cnt+1
    fi

    return $cnt
}

function verify_prefixes {
    controller_arg=${1}

    if [ ! -e ${controller_arg}/.prefix ]; then
        return 0
    fi
    if [ ! -d ${controller_arg}/.prefix ]; then
        printf "\t* Prefix directory, .prefix, is not a directory!\n"
        return 1
    fi

    let cnt=0

    find ${controller_arg}/.prefix -maxdepth 1 \
            \( ! -name 'prefix.*' ! -name '*.prefix' -fprintf ${non_prefixes}.unsorted "\t  %f\n" \) \
            -o \( -name 'prefix.*' -fprintf ${wrong_prefixes}.unsorted "\t  %f\n" \)
    status=$?
    if [ $status -ne 0 ]; then
        printf "*** ERROR *** unable to traverse ${controller_arg}/.prefix: find failed with $status\n"
        let cnt=cnt+1
    fi

    sort ${non_prefixes}.unsorted > ${non_prefixes} 2>&1
    if [ -s ${non_prefixes} ]; then
        printf "\t* Unexpected file system objects in .prefix directory:\n"
        printf "\t  ++++++++++\n"
        cat ${non_prefixes}
        printf "\t  ----------\n"
        let cnt=cnt+1
    fi
    rm -f ${non_prefixes} ${non_prefixes}.unsorted

    sort ${wrong_prefixes}.unsorted > ${wrong_prefixes} 2>&1
    if [ -s ${wrong_prefixes} ]; then
        printf "\t* Wrong prefix file names found in /.prefix directory:\n"
        printf "\t  ++++++++++\n"
        cat ${wrong_prefixes}
        printf "\t  ----------\n"
        let cnt=cnt+1
    fi
    rm -f ${wrong_prefixes} ${wrong_prefixes}.unsorted

    return $cnt
}

function verify_incoming {
    controllers_arg=${1}

    let cnt=0

    while read controller ;do
        if [ ! -d $ARCHIVE/${controller} ]; then
            # Skip incoming controller directories that don't have an $ARCHIVE
            # directory, handled in another part of the audit.
            continue
        fi
        lclreport="${workdir}/$(basename ${controller})"
        > ${lclreport}

        tarball_dirs="${workdir}/tarballdirs"
        empty_tarball_dirs="${workdir}/emptytarballdirs"
        > ${empty_tarball_dirs}.unsorted
        tarball_links="${workdir}/tarballlinks"
        find $INCOMING/${controller} -maxdepth 1 \
                \( -type d ! -name ${controller} ! -empty -fprintf ${tarball_dirs} "%f\n" \) \
                -o \( -type d ! -name ${controller} -empty -fprintf ${empty_tarball_dirs}.unsorted "\t\t%f\n" \) \
                -o \( -type l -fprintf ${tarball_links} "%f %l\n" \)
        status=$?
        if [ $status -ne 0 ]; then
            printf "*** ERROR *** unable to traverse $INCOMING/${controller}: find failed with $status" >> ${lclreport}
            let cnt=cnt+1
        fi

        invalid_tb_dirs="${workdir}/invalidtbdirs"
        > ${invalid_tb_dirs}.unsorted
        while read tb ; do
            if [ -f $ARCHIVE/${controller}/${tb}.tar.xz ]; then
                continue
            fi
            printf "\t\t${tb}\n" >> ${invalid_tb_dirs}.unsorted
        done < ${tarball_dirs}
        rm ${tarball_dirs}

        if [ -s ${invalid_tb_dirs}.unsorted ]; then
            printf "\tInvalid tar ball directories (not in $ARCHIVE):\n" >> ${lclreport}
            sort ${invalid_tb_dirs}.unsorted >> ${lclreport}
        fi
        rm ${invalid_tb_dirs}.unsorted

        if [ -s ${empty_tarball_dirs}.unsorted ]; then
            printf "\tEmpty tar ball directories:\n" >> ${lclreport}
            sort ${empty_tarball_dirs}.unsorted >> ${lclreport}
        fi
        rm ${empty_tarball_dirs}.unsorted

        invalid_tb_dir_links="${workdir}/invalidtbdirlinks"
        > ${invalid_tb_dir_links}.unsorted
        while read tb link ; do
            # The link in the incoming directory does not point to
            # the expected directory in the unpack hierarchy.
            printf "\t\t${tb}\n" >> ${invalid_tb_dir_links}.unsorted
        done < ${tarball_links}
        rm ${tarball_links}

        if [ -s ${invalid_tb_dir_links}.unsorted ]; then
            printf "\tInvalid tar ball links:\n" >> ${lclreport}
            sort ${invalid_tb_dir_links}.unsorted >> ${lclreport}
        fi
        rm ${invalid_tb_dir_links}.unsorted

        if [ -s ${lclreport} ]; then
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

    if [ -z ${user_arg} ]; then
        results_hierarchy=$RESULTS
    else
        results_hierarchy=$USERS/${user_arg}
    fi

    let cnt=0

    while read controller ;do
        if [ ! -d $ARCHIVE/${controller} ]; then
            # Skip incoming controller directories that don't have an $ARCHIVE
            # directory, handled in another part of the audit.
            continue
        fi
        lclreport="${workdir}/$(basename ${controller})"
        > ${lclreport}

        # The hierarchy of a controller in the results tree should only
        # contain directories and symlinks, where symlinks could be anywhere
        # in the hierarchy of directories, as long as the path from the
        # controller directory to the symlink is defined by a prefix file. If
        # no prefix file exists, then the default of a symlink in the
        # controller is all that should exist for a given tar ball.
        empty_tarball_dirs="${workdir}/emptytarballdirs"
        > ${empty_tarball_dirs}.unsorted
        tarball_links="${workdir}/tarballlinks"
        > ${tarball_links}
        find ${results_hierarchy}/${controller} \
                \( -type d ! -name ${controller} -empty -fprintf ${empty_tarball_dirs}.unsorted "\t\t%P\n" \) \
                -o \( -type l -fprintf ${tarball_links} "%P %l\n" \)
        status=$?
        if [ $status -ne 0 ]; then
            printf "*** ERROR *** unable to traverse ${results_hierarchy}/${controller}: find failed with $status" >> ${lclreport}
            let cnt=cnt+1
        fi

        sort ${empty_tarball_dirs}.unsorted > ${empty_tarball_dirs}
        if [ -s ${empty_tarball_dirs} ]; then
            printf "\tEmpty tar ball directories:\n" >> ${lclreport}
            cat ${empty_tarball_dirs} >> ${lclreport}
        fi
        rm ${empty_tarball_dirs}.unsorted ${empty_tarball_dirs}

        # Verify the link name should be a link to the $INCOMING directory or
        # a symlink of the same name, and should be the name of a valid tar
        # ball.
        invalid_tb_links="${workdir}/invalidtblinks"
        > ${invalid_tb_links}
        incorrect_tb_dir_links="${workdir}/incorrecttbdirlinks"
        > ${incorrect_tb_dir_links}
        invalid_tb_dir_links="${workdir}/invalidtbdirlinks"
        > ${invalid_tb_dir_links}
        unused_prefix_files="${workdir}/unusedprefixfiles"
        > ${unused_prefix_files}
        missing_prefix_files="${workdir}/missingprefixfiles"
        > ${missing_prefix_files}
        bad_prefix_files="${workdir}/badprefixfiles"
        > ${bad_prefix_files}
        bad_prefixes="${workdir}/badprefixes"
        > ${bad_prefixes}
        unexpected_user_links="${workdir}/unexpecteduserlinks"
        > ${unexpected_user_links}
        wrong_user_links="${workdir}/wronguserlinks"
        > ${wrong_user_links}
        while read path link ; do
            tb=$(basename ${path})
            if [ ! -e $ARCHIVE/${controller}/${tb}.tar.xz ]; then
                # The tar ball does not exist in the archive hierarchy.
                printf "\t\t${path}\n" >> ${invalid_tb_links}
            else
                if [ "${link}" != "$INCOMING/${controller}/${tb}" ]; then
                    # The link is not constructed to point to the proper
                    # location in the incoming hierarchy.
                    printf "\t\t${path}\n" >> ${incorrect_tb_dir_links}
                elif [ ! -d $INCOMING/${controller}/${tb} -a ! -L $INCOMING/${controller}/${tb} ]; then
                    # The link in the results directory does not point to
                    # a directory or link in the incoming hierarchy.
                    printf "\t\t${path}\n" >> ${invalid_tb_dir_links}
                else
                    prefix_path=$(dirname ${path})
                    prefix_file="$ARCHIVE/${controller}/.prefix/${tb}.prefix"
                    # Version 002 agents use the metadata log to store a
                    # prefix.
                    prefix=$(getconf.py -C $INCOMING/${controller}/${tb}/metadata.log prefix run)
                    if [ "${prefix_path}" == "." ]; then
                        # No prefix, ensure it doesn't have a prefix in the
                        # metadata.log file or in a prefix file.
                        if [ ! -z "${prefix}" ]; then
                            # The stored prefix does not match the
                            # actual prefix
                            printf "\t\t${path}\n" >> ${bad_prefixes}
                        elif [ -e ${prefix_file} ]; then
                            printf "\t\t${path}\n" >> ${unused_prefix_files}
                        fi
                    else
                        # Have a prefix ...
                        if [ ! -z "${prefix}" ]; then
                            # Have a prefix in the metadata.log file ...
                            if [ ${prefix} != ${prefix_path} ]; then
                                # The stored prefix does not match the
                                # actual prefix
                                printf "\t\t${path}\n" >> ${bad_prefixes}
                            fi
                        elif [ ! -e ${prefix_file} ]; then
                            # Don't have a prefix file either.
                            printf "\t\t${path}\n" >> ${missing_prefix_files}
                        else
                            # Ensure we can actually read from the expected
                            # prefix file
                            prefix=$(cat ${prefix_file} 2> /dev/null)
                            if [ $? -gt 0 ]; then
                                printf "\t\t${path}\n" >> ${bad_prefix_files}
                            else
                                if [ ${prefix} != ${prefix_path} ]; then
                                    # The stored prefix does not match the
                                    # actual prefix
                                    printf "\t\t${path}\n" >> ${bad_prefixes}
                                fi
                            fi
                        fi
                    fi
                    if [ ! -z "${user_arg}" ]; then
                        # We are reviewing a user tree, so check the user in
                        # the configuration.  Version 002 agents use the
                        # metadata log to store a user as well.
                        user=$(getconf.py -C $INCOMING/${controller}/${tb}/metadata.log user run)
                        if [ -z "${user}" ]; then
                            # No user in the metadata.log of the tar ball, but
                            # we are examining a link in the user tree that
                            # does not have a configured user, report it.
                            printf "\t\t${path}\n" >> ${unexpected_user_links}
                        elif [ "${user_arg}" != "${user}" ]; then
                            # Configured user does not match the user tree in
                            # which we found the link.
                            printf "\t\t${path}\n" >> ${wrong_user_links}
                        fi
                    fi
                fi
            fi
        done < ${tarball_links}
        rm ${tarball_links}

        if [ -s ${invalid_tb_links} ]; then
            printf "\tInvalid tar ball links (not in $ARCHIVE):\n" >> ${lclreport}
            cat ${invalid_tb_links} >> ${lclreport}
        fi
        rm ${invalid_tb_links}

        if [ -s ${incorrect_tb_dir_links} ]; then
            printf "\tIncorrectly constructed tar ball links:\n" >> ${lclreport}
            cat ${incorrect_tb_dir_links} >> ${lclreport}
        fi
        rm ${incorrect_tb_dir_links}

        if [ -s ${invalid_tb_dir_links} ]; then
            printf "\tTar ball links to invalid incoming location:\n" >> ${lclreport}
            cat ${invalid_tb_dir_links} >> ${lclreport}
        fi
        rm ${invalid_tb_dir_links}

        if [ -s ${unused_prefix_files} ]; then
            printf "\tTar ball links with unused prefix files:\n" >> ${lclreport}
            cat ${unused_prefix_files} >> ${lclreport}
        fi
        rm ${unused_prefix_files}

        if [ -s ${missing_prefix_files} ]; then
            printf "\tTar ball links with missing prefix files:\n" >> ${lclreport}
            cat ${missing_prefix_files} >> ${lclreport}
        fi
        rm ${missing_prefix_files}

        if [ -s ${bad_prefix_files} ]; then
            printf "\tTar ball links with bad prefix files:\n" >> ${lclreport}
            cat ${bad_prefix_files} >> ${lclreport}
        fi
        rm ${bad_prefix_files}

        if [ -s ${bad_prefixes} ]; then
            printf "\tTar ball links with bad prefixes:\n" >> ${lclreport}
            cat ${bad_prefixes} >> ${lclreport}
        fi
        rm ${bad_prefixes}

        if [ -s ${unexpected_user_links} ]; then
            printf "\tTar ball links not configured for this user:\n" >> ${lclreport}
            cat ${unexpected_user_links} >> ${lclreport}
        fi
        rm ${unexpected_user_links}

        if [ -s ${wrong_user_links} ]; then
            printf "\tTar ball links for the wrong user:\n" >> ${lclreport}
            cat ${wrong_user_links} >> ${lclreport}
        fi
        rm ${wrong_user_links}

        if [ -s ${lclreport} ]; then
            if [ ! -z "${user_arg}" ]; then
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
    # Assert that $1/ only contains controller directories, and that each
    # directory has a $ARCHIVE/ directory that exists as a directory.
    hierarchy_root=${1}

    if [ "${hierarchy_root}" = "$INCOMING" ]; then
        kind="incoming"
        user=""
    elif [ "${hierarchy_root}" = "$RESULTS" ]; then
        kind="results"
        user=""
    elif [ "$(dirname ${hierarchy_root})" = "$USERS" ]; then
        kind="results"
        user=$(basename ${hierarchy_root})
    else
        printf "${PROG}: verify_controllers bad argument, hierarchy_root=\"${hierarchy_root}\"\n" >&2
        return 1
    fi

    let cnt=0

    # Find all the normal controller directories, ignoring the "." (current)
    # directory (if the $hierarchy_root directory resolves to "."), and
    # ignoring the $hierarchy_root directory itself, while keeping them all
    # in sorted order.
    > ${unexpected_objects}.unsorted
    > ${controllers}.unsorted
    find ${hierarchy_root} -maxdepth 1 \
            \( ! -type d -fprintf ${unexpected_objects}.unsorted "\t%f\n" \) \
            -o \( -type d ! -name . ! -name $(basename ${hierarchy_root}) -fprintf ${controllers}.unsorted "%f\n" \)
    status=$?
    if [ $status -ne 0 ]; then
        printf "*** ERROR *** unable to traverse hiearchy ${hierarchy_root}: find failed with $status\n"
        let cnt=cnt+1
    fi

    sort ${unexpected_objects}.unsorted > ${unexpected_objects}
    if [ -s ${unexpected_objects} ]; then
        printf "\nUnexpected files found:\n"
        cat ${unexpected_objects}
        let cnt=cnt+1
    fi
    rm -f ${unexpected_objects}.unsorted ${unexpected_objects}

    sort ${controllers}.unsorted > ${controllers}
    if [ -s ${controllers} ]; then
        mialist="${workdir}/missing_in_archive"
        > ${mialist}
        emptylist="${workdir}/empty_controllers"
        > ${emptylist}
        unexpectedlist="${workdir}/controllers_w_unexpected"
        > ${unexpectedlist}
        verifylist="${workdir}/controllers_to_verify"
        > ${verifylist}
        while read controller ;do
            if [ ! -d ${ARCHIVE}/${controller} ]; then
                # We have a controller in the hierarchy which does not have a
                # controller of the same name in the archive hierarchy.  All
                # we do is report it, don't bother analyzing it further.
                printf "\t${controller}\n" >> ${mialist}
            else
                # Report any controllers with objects other than directories
                # and links, while also recording any empty controllers.
                > ${unexpected_objects}
                > ${empty}
                find ${hierarchy_root}/${controller} -maxdepth 1 \
                        \( ! -type d ! -type l -fprintf ${unexpected_objects} "%f\n" \) \
                        -o \( -type d -name ${controller} -empty -fprintf ${empty} "%f\n" \)
                status=$?
                if [ $status -ne 0 ]; then
                    printf "*** ERROR *** unable to traverse hiearchy ${hierarchy_root}/${controller}: find failed with $status\n"
                    let cnt=cnt+1
                fi
                if [ -s "${empty}" ]; then
                    printf "\t${controller}\n" >> ${emptylist}
                elif [ -s "${unexpected_objects}" ]; then
                    printf "\t${controller}\n" >> ${unexpectedlist}
                    printf "\t${controller}\n" >> ${verifylist}
                else
                    printf "\t${controller}\n" >> ${verifylist}
                fi
                rm -f ${unexpected_objects} ${empty}
            fi
        done < ${controllers}

        if [ -s "${mialist}" ]; then
            printf "\nControllers which do not have a ${ARCHIVE} directory:\n"
            cat ${mialist}
            let cnt=cnt+1
        fi
        rm -f ${mialist}
        if [ -s "${emptylist}" ]; then
            printf "\nControllers which are empty:\n"
            cat ${emptylist}
            let cnt=cnt+1
        fi
        rm -f ${emptylist}
        if [ -s "${unexpectedlist}" ]; then
            printf "\nControllers which have unexpected objects:\n"
            cat ${unexpectedlist}
            let cnt=cnt+1
        fi
        rm -f ${unexpectedlist}
        if [ -s "${verifylist}" ]; then
            verify_${kind} ${verifylist} ${user}
            if [ $? -gt 0 ]; then
                let cnt=cnt+1
            fi
        fi
        rm -f ${verifylist}
    fi
    rm -f ${controllers}.unsorted ${controllers}

    return $cnt
}

function verify_users {
    let cnt=0

    # The $USERS hierarchy should only contain directories at the first
    # level, which themselves should be just like a sub-set of the
    # $RESULTS tree.
    > ${unexpected_objects}.unsorted
    > ${users}.unsorted
    find $USERS -maxdepth 1 \
            \( ! -type d -fprintf ${unexpected_objects}.unsorted "\t%f\n" \) \
            -o \( -type d ! -name . ! -name $(basename $USERS) -fprintf ${users}.unsorted "%f\n" \)
    status=$?
    if [ $status -ne 0 ]; then
        printf "*** ERROR *** unable to traverse hiearchy $USERS: find failed with $status\n"
        let cnt=cnt+1
    fi

    sort ${unexpected_objects}.unsorted > ${unexpected_objects}
    if [ -s ${unexpected_objects} ]; then
        printf "\nUnexpected files found:\n"
        cat ${unexpected_objects}
        let cnt=cnt+1
    fi
    rm -f ${unexpected_objects}.unsorted ${unexpected_objects}

    sort ${users}.unsorted > ${users}
    while read user ;do
        verify_controllers $USERS/${user}
        if [ $? -gt 0 ]; then
            let cnt=cnt+1
        fi
    done < ${users}
    rm -f ${users}.unsorted ${users}

    return $cnt
}

function verify_archive {
    let cnt=0

    # Find all the non-directory files at the same level of the controller
    # directories and report them, keeping them in sorted order by name, and
    # find all the normal controller directories, ignoring the "." (current)
    # directory (if the $ARCHIVE directory resolves to "."), and ignoring the
    # $ARCHIVE directory itself, while keeping them all in sorted order.
    > ${bad_controllers}.unsorted
    > ${controllers}.unsorted
    find $ARCHIVE -maxdepth 1 \
         \( ! -type d -fprintf ${bad_controllers}.unsorted "\t%M %10s %t %f\n" \) \
         -o \( -type d ! -name . ! -name $(basename $ARCHIVE) -fprintf ${controllers}.unsorted "%p\n" \)
    if [ $? -gt 0 ]; then
        printf "\n*** ERROR *** unable to traverse $ARCHIVE hierarchy\n"
        let cnt=cnt+1
    fi

    sort -k 8 ${bad_controllers}.unsorted > ${bad_controllers}
    if [ -s ${bad_controllers} ]; then
        printf "\nBad Controllers:\n"
        cat ${bad_controllers}
        let cnt=cnt+1
    fi
    rm -f ${bad_controllers}.unsorted ${bad_controllers}

    # Find all the normal controller directories, ignoring the "." (current)
    # directory (if the $ARCHIVE directory resolves to "."), and ignoring the
    # $ARCHIVE directory itself, while keeping them all in sorted order.
    sort ${controllers}.unsorted > ${controllers}
    while read controller ;do
        lclreport="${workdir}/$(basename ${controller})"
        > ${lclreport}

        > ${directories}.unsorted
        > ${unexpected_symlinks}.unsorted
        > ${unexpected_objects}.unsorted
        > ${tarballs}
        find ${controller} -maxdepth 1 \
                \( -type d ! -name . ! -name $(basename ${controller}) ! -name .prefix -fprintf ${directories}.unsorted "\t  %f\n" \) \
                -o \( -type l -fprintf ${unexpected_symlinks}.unsorted "\t  %f -> %l\n" \) \
                -o \( -type f ! -name '*.tar.xz.md5' ! -name '*.tar.xz' -fprintf ${unexpected_objects}.unsorted "\t  %f\n" \) \
                -o \( -type f \( -name '*.tar.xz.md5' -o -name '*.tar.xz' \) -fprintf ${tarballs} "%f\n" \)
        status=$?
        if [ $status -gt 0 ]; then
            printf "*** ERROR *** unable to traverse controller hierarchy for $(basename ${controller}): find failed with $status\n" >> ${lclreport}
            let cnt=cnt+1
        else
            sort ${directories}.unsorted > ${directories}
            verify_subdirs ${directories} >> ${lclreport}

            sort ${unexpected_symlinks}.unsorted > ${unexpected_symlinks}
            sort ${unexpected_objects}.unsorted > ${unexpected_objects}
            verify_tarball_names ${unexpected_symlinks} ${unexpected_objects} ${tarballs} >> ${lclreport}

            verify_prefixes ${controller} >> ${lclreport}
        fi
        rm -f ${directories}.unsorted ${directories}
        rm -f ${unexpected_symlinks}.unsorted ${unexpected_symlinks}
        rm -f ${unexpected_objects}.unsorted ${unexpected_objects}
        rm -f ${tarballs}

        if [ -s ${lclreport} ]; then
            printf "\nController: $(basename ${controller})\n"
            cat ${lclreport}
            let cnt=cnt+1
        fi
        rm ${lclreport}
    done < ${controllers}
    rm -f ${controllers}.unsorted ${controllers}

    return $cnt
}

log_init $PROG

# Initialize index mail content
> ${index_content}
> ${report}

let ret=0

# Construct the report file
sTS=$(timestamp)
verify_archive > ${archive_report} 2>&1
if [ $? -ne 0 ]; then
    let ret=ret+1
fi
eTS=$(timestamp)
if [ -s ${archive_report} ]; then
    printf "\nstart-${sTS}: archive hierarchy: $ARCHIVE\n" | tee -a ${report}
    cat ${archive_report} | tee -a ${report}
    printf "\nend-${eTS}: archive hierarchy: $ARCHIVE\n" | tee -a ${report}
fi

sTS=$(timestamp)
verify_controllers $INCOMING > ${incoming_report} 2>&1
if [ $? -ne 0 ]; then
    let ret=ret+1
fi
eTS=$(timestamp)
if [ -s ${incoming_report} ]; then
    printf "\n\nstart-${sTS}: incoming hierarchy: $INCOMING\n" | tee -a ${report}
    cat ${incoming_report} | tee -a ${report}
    printf "\nend-${eTS}: incoming hierarchy: $INCOMING\n" | tee -a ${report}
fi

sTS=$(timestamp)
verify_controllers $RESULTS > ${results_report} 2>&1
if [ $? -ne 0 ]; then
    let ret=ret+1
fi
eTS=$(timestamp)
if [ -s ${results_report} ]; then
    printf "\n\nstart-${sTS}: results hierarchy: $RESULTS\n" | tee -a ${report}
    cat ${results_report} | tee -a ${report}
    printf "\nend-${eTS}: results hierarchy: $RESULTS\n" | tee -a ${report}
fi

sTS=$(timestamp)
verify_users > ${users_report} 2>&1
if [ $? -ne 0 ]; then
    let ret=ret+1
fi
eTS=$(timestamp)
if [ -s ${users_report} ]; then
    printf "\n\nstart-${sTS}: users hierarchy: $USERS\n" | tee -a ${report}
    cat ${users_report} | tee -a ${report}
    printf "\nend-${eTS}: users hierarchy: $USERS\n" | tee -a ${report}
fi

log_finish

# send it
subj="$PROG.$TS($PBENCH_ENV)"
cat << EOF > ${index_content}
$subj
EOF

cat ${report} >> ${index_content}
pbench-report-status --name $PROG --timestamp $(timestamp) --type status ${index_content}

exit $ret
