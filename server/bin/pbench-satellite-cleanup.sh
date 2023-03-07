#! /bin/bash

# load common things
. $dir/pbench-base.sh

test -d "${ARCHIVE}"  || doexit "Bad ARCHIVE=${ARCHIVE}"
test -d "${INCOMING}" || doexit "Bad INCOMING=${INCOMING}"
test -d "${RESULTS}"  || doexit "Bad RESULTS=${RESULTS}"

tmp=$(get-tempdir-name $PROG)
mkdir -p "$tmp" || doexit "Failed to create $tmp"
trap "rm -rf $tmp" EXIT

log_init $PROG

start_ts=$(timestamp)

tarballs=$(cd $ARCHIVE > /dev/null; find . -path '*/TO-DELETE/*.tar.xz' -printf '%P\n' | sort)
hosts="$(for host in $tarballs ;do echo "${host%%/*}" ;done | sort -u )"

typeset -i nhosts=0
typeset -i ntbs=0
typeset -i ntberrs=0
typeset -i nmd5errs=0
typeset -i nstateerrs=0
typeset -i nincomingerrs=0
typeset -i nresultserrs=0

for host in $hosts; do
    (( nhosts++ ))
    pushd $ARCHIVE/$host > /dev/null || log_exit "Failed to pushd to $ARCHIVE/$host"
    mkdir -p SATELLITE-DONE > /dev/null || log_exit "Failed to create $ARCHIVE/$host/SATELLITE-DONE"
    for tb in $tarballs; do
        if [ "$host" != "${tb%%/*}" ]; then
            continue
        fi
        (( ntbs++ ))
        x=${tb##*/}
        # remove tar file
        if [ -e $x ]; then
            rm $x
            rc=$?
            if [ $rc != 0 ]; then
                # We failed to remove the tarball; we just continue the loop but
                # we'll send mail with the failure. Hopefully, the next time
                # around we'll succeed (presumably because the admins will have
                # taken some action).
                #
                # OTOH, if we fail to remove any of the other related files /
                # directories, we'll go on and try to delete the rest of them. If
                # we manage to change the state, there might be remnants to clean
                # up manually. The error mail will identify those.
                #
                # Note that if we do remove the tarball but fail to change the
                # state, this error will persist until the state is changed
                # manually.
                log_error "$TS: Failed to remove $ARCHIVE/$host/$x, code: $rc"
                (( ntberrs++ ))
                popd > /dev/null 2>&4
                continue
            fi
        fi
        # remove its md5
        if [ -e $x.md5 ]; then
            rm $x.md5
            rc=$?
            if [ $rc != 0 ]; then
                log_error "$TS: Failed to remove $ARCHIVE/$host/$x.md5, code: $rc"
                (( nmd5errs++ ))
            fi
        fi
        # change the state to SATELLITE-DONE
        if [ -L TO-DELETE/$x ]; then
            mv -n TO-DELETE/$x SATELLITE-DONE/
            rc=$?
            if [ $rc != 0 ]; then
                log_error "$TS: Failed to move $ARCHIVE/$host/TO-DELETE/$x to SATELLITE-DONE, code: $rc"
                (( nstateerrs++ ))
            else
                if [ -e TO-DELETE/$x ]; then
                    log_error "$TS: Failed to move $ARCHIVE/$host/TO-DELETE/$x: still exists after successful move to SATELLITE-DONE"
                    (( nstateerrs++ ))
                fi
            fi
        fi
        # remove from incoming
        if [ -e $INCOMING/$host/${x%%.tar.xz} ]; then
            rm -rf $INCOMING/$host/${x%%.tar.xz}
            rc=$?
            if [ $rc != 0 ]; then
                log_error "$TS: Failed to remove the tarball from incoming directory: $INCOMING/$host/${x%%.tar.xz}, code: $rc"
                (( nincomingerrs++ ))
            fi
        fi
        # remove the results
        sym_link=$RESULTS/$host/${x%%.tar.xz}
        if [ -L $sym_link ]; then
            rm $sym_link
            rc=$?
            if [ $rc != 0 ]; then
                log_error "$TS: Failed to remove results symlink: $sym_link, code: $rc"
                (( nresultserrs++ ))
            fi
        fi
    done
    popd > /dev/null 2>&4
done

end_ts=$(timestamp)

if [[ ${ntbs} -gt 0 ]]; then
    summary_text="(${PBENCH_ENV})"
    summary_text+=" Total ${ntbs} tar balls cleaned up (for ${nhosts} hosts),"
    summary_text+=" with ${ntberrs} tar ball removal errors, ${nmd5errs} md5"
    summary_text+=" file removal errors, ${nstateerrs} state change errors,"
    summary_text+=" ${nincomingerrs} incoming directory removal errors, and"
    summary_text+=" ${nresultserrs} result directory removal errors."
    printf -v summary_inner_json \
        "{\"%s\": \"%s\", \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": %d, \"%s\": \"%s\", \"%s\": \"%s\", \"%s\": \"%s\"}" \
        "end_ts" "${end_ts}" \
        "errors" "$((nincomingerrs+nmd5errs+nresultserrs+nstateerrs+ntberrs))" \
        "nhosts" "${nhosts}" \
        "nincomingerrs" "${nincomingerrs}" \
        "nmd5errs" "${nmd5errs}" \
        "nresultserrs" "${nresultserrs}" \
        "nstateerrs" "${nstateerrs}" \
        "ntbs" "${ntbs}" \
        "ntberrs" "${ntberrs}" \
        "prog" "${PROG}" \
        "start_ts" "${start_ts}" \
        "text" "${summary_text}"
    printf -v summary_json "{\"pbench\": {\"report\": {\"summary\": %s}}}" "${summary_inner_json}"

    log_info "@cee:${summary_json}"
fi

log_finish

exit 0
