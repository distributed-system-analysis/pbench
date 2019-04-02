#! /bin/bash

# load common things
. $dir/pbench-base.sh

test -d $ARCHIVE || doexit "Bad ARCHIVE=$ARCHIVE"
test -d $INCOMING || doexit "Bad INCOMING=$INCOMING"
test -d $RESULTS || doexit "Bad RESULTS=$RESULTS"

tmp=$(get-tempdir-name $PROG)
mkdir -p "$tmp" || doexit "Failed to create $tmp"
trap "rm -rf $tmp" EXIT

log_init $PROG

echo "$TS: $PROG starting"

tarballs=$(cd $ARCHIVE > /dev/null; find . -path '*/TO-DELETE/*.tar.xz' -printf '%P\n' | sort)
hosts="$(for host in $tarballs ;do echo "${host%%/*}" ;done | sort -u )"

typeset -i ntb=0
typeset -i nerrs=0
typeset -i ntberrs=0
typeset -i nmd5errs=0
typeset -i nstateerrs=0
typeset -i nincomingerrs=0
typeset -i nresultserrs=0
typeset -i nprefixerrs=0

mail_content=$tmp/mail.log
index_content=$tmp/index_mail_contents

# Initialize mail content
> $mail_content
> $index_content

for host in $hosts; do
    pushd $ARCHIVE/$host > /dev/null || log_exit "Failed to pushd to $ARCHIVE/$host"
    mkdir -p SATELLITE-DONE > /dev/null || log_exit "Failed to create $ARCHIVE/$host/SATELLITE-DONE"
    for tb in $tarballs; do
        if [ "$host" != "${tb%%/*}" ]; then
            continue
        fi
        ntb=$ntb+1
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
                echo "$TS: Failed to remove $ARCHIVE/$host/$x, code: $rc" |
                        tee -a $mail_content >&4
                ntberrs=$ntberrs+1
                popd > /dev/null 2>&4
                continue
            fi
        fi
        # remove its md5
        if [ -e $x.md5 ]; then
            rm $x.md5
            rc=$?
            if [ $rc != 0 ]; then
                echo "$TS: Failed to remove $ARCHIVE/$host/$x.md5, code: $rc" |
                        tee -a $mail_content >&4
                nmd5errs=$nmd5errs+1
            fi
        fi
        # change the state to SATELLITE-DONE
        if [ -L TO-DELETE/$x ]; then
            mv -n TO-DELETE/$x SATELLITE-DONE/
            rc=$?
            if [ $rc != 0 ]; then
                echo "$TS: Failed to move $ARCHIVE/$host/TO-DELETE/$x to SATELLITE-DONE, code: $rc" |
                        tee -a $mail_content >&4
                nstateerrs=$nstateerrs+1
            else
                if [ -e TO-DELETE/$x ]; then
                    echo "$TS: Failed to move $ARCHIVE/$host/TO-DELETE/$x: still exists after successful move to SATELLITE-DONE" |
                            tee -a $mail_content >&4
                    nstateerrs=$nstateerrs+1
                fi
            fi
        fi
        # remove from incoming
        if [ -e $INCOMING/$host/${x%%.tar.xz} ]; then
            rm -rf $INCOMING/$host/${x%%.tar.xz}
            rc=$?
            if [ $rc != 0 ]; then
                echo "$TS: Failed to remove the tarball from incoming directory: $INCOMING/$host/${x%%.tar.xz}, code: $rc" |
                        tee -a $mail_content >&4
                nincomingerrs=$nincomingerrs+1
            fi
        fi
        # remove the results
        prefix=".prefix/${x%%.tar.xz}.prefix"
        if [ -e $prefix ]; then
            prefix_value=$(cat ".prefix/${x%%.tar.xz}.prefix")
        else
            prefix_value=""
        fi
        if [ -z "$prefix_value" ]; then
            sym_link=$RESULTS/$host/${x%%.tar.xz}
        else
            sym_link=$RESULTS/$host/$prefix_value/${x%%.tar.xz}
        fi
        if [ -L $sym_link ]; then
            rm $sym_link
            rc=$?
            if [ $rc != 0 ]; then
                echo "$TS: Failed to remove results symlink: $sym_link, code: $rc" |
                        tee -a $mail_content >&4
                nresultserrs=$nresultserrs+1
            fi
        fi
        # remove prefix if present
        if [ -e $prefix ]; then
            rm $prefix
            rc=$?
            if [ $rc != 0 ]; then
                echo "$TS: Failed to remove prefix file: $prefix, code: $rc" |
                        tee -a $mail_content >&4
                nprefixerrs=$nprefixerrs+1
            fi
        fi
    done
    popd > /dev/null 2>&4
done

summary="Total $ntb tarballs cleaned up, with $ntberrs tarball removal errors, $nmd5errs md5 file \
remove errors, $nstateerrs state change errors, $nincomingerrs incoming removal errors, $nresultserrs \
result removal errors and $nprefixerrs prefix removal errors."

echo "$TS: $PROG ends: $summary"

log_finish

nerrs=$ntberrs+$nmd5errs+$nstateerrs+$nincomingerrs+$nresultserrs+$nprefixerrs

subj="$PROG.$TS($PBENCH_ENV) - w/ $nerrs total errors"
cat << EOF > $index_content
$subj
$summary

EOF
cat $mail_content >> $index_content
pbench-report-status --name $PROG --timestamp $TS --type status $index_content

exit 0
