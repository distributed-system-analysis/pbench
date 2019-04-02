#! /bin/bash
# -*- mode: shell-script -*-

# This script is the third part of the pipeline that processes pbench
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
#   the $ARCHIVE/$(hostname -s) area.
# - move/copy-results also makes a symlink to each tarball it uploads
#   in $ARCHIVE/TODO.

# This script loops over the contents of $archive/<hostname>/TO-INDEX,
# extracts the information from the tarball and calls an indexing script
# to index the results into ES. If everything works, it then moves the
# symlink from $ARCHIVE/<hostname>/TO-INDEX to $ARCHIVE/<hostname>/DONE.

# load common things
. $dir/pbench-base.sh

# check that all the directories exist
test -d $ARCHIVE || doexit "Bad ARCHIVE=$ARCHIVE"

# index-pbench depends on a whole hierarchy - this script and index-pbench
# are in /opt/pbench-server/bin when deployed, but it depends on
# /opt/pbench-server/lib/config/pbench-server.cfg,
# /opt/pbench-server/lib/vos etc.  Also, index-pbench requires python3:
# that's available on Fedora but, for RHEL, we need software collections.
PROGLOC=$(getconf.py install-dir pbench-server)
test -d $PROGLOC || doexit "Bad [pbench-server] install-dir=$PROGLOC"

log_init $PROG

# make sure only one copy is running.
# Use 'flock -n $LOCKFILE /home/pbench/bin/pbench-index' in the
# crontab to ensure that only one copy is running. The script itself
# does not use any locking.

# the link source and destination for this script
linksrc=TO-INDEX
linkdest=INDEXED
linkerrdest=WONT-INDEX

WRKDIR=$TMP/pbench-index.$$
# index-pbench uses TMPDIR as the location to extract tar balls; give it a
# dedicated sub-directory to work with as its temporary directory.
TMPDIR=$WRKDIR/extractions
export TMPDIR

echo "$TS: starting at $(timestamp)"

typeset -i nidx=0
indexed=$WRKDIR/$PROG.$TS.indexed
typeset -i nerrs=0
erred=$WRKDIR/$PROG.$TS.erred
typeset -i nskip=0
skipped=$WRKDIR/$PROG.$TS.skipped
report_body=$WRKDIR/$PROG.$TS.report
errors_json=$WRKDIR/$PROJ.$TS.indexing-errors.json

mkdir -p $WRKDIR
trap "rm -rf $WRKDIR" EXIT QUIT INT

> $indexed
> $erred
> $skipped
> $errors_json

list=$WRKDIR/list
find -L $ARCHIVE/*/$linksrc -name '*.tar.xz' -printf "%s\t%p\n" 2>/dev/null | sort -n > $list

while read size result ;do
    echo "   $(timestamp): Starting $result (size $size)"
    link=$(readlink -e $result)
    if [[ -z "${link}" ]] ;then
        echo "$TS: invalid symlink ${result}" >&4
        nerrs=$nerrs+1
        echo $result >> $erred
        continue
    fi
    if [[ ! -f "${link}" || ! -f "${link}.md5" ]] ;then
        echo "$TS: ${link} and/or ${link}.md5 does not exist for ${result}" >&4
        nerrs=$nerrs+1
        echo $result >> $erred
        continue
    fi

    resultname=$(basename $result)
    resultname=${resultname%.tar.xz}
    controller_path=$(dirname ${link})
    hostname=$(basename ${controller_path})

    # make sure that all the relevant state directories exist
    mk_dirs $hostname

    # Ensure we can create the TMPDIR used for extracted tar balls each time
    # we call index-pbench to help ensure everything operates cleanly and we
    # only have one tar ball extracted at a time.
    mkdir $TMPDIR || doexit "Bad $TMPDIR"

    python3 ${PROGLOC}/bin/index-pbench --config ${PROGLOC}/lib/config/pbench-server.cfg -E $errors_json ${@} $link
    status=$?
    if [ -s $errors_json ]; then
        echo $link > $errors_json.report
        cat $errors_json >> $errors_json.report
        pbench-report-status --name $PROG.errors --timestamp $TS --type status $errors_json.report
        rm -f $errors_json.report
        > $errors_json
    fi

    # Exit if index-pbench fails to clean up properly.
    rmdir $TMPDIR || doexit "Non-empty $TMPDIR"

    if [ $status -ne 0 ] ;then
        # Distinguish failure cases, so we can retry the indexing easily if possible.
        # Different WONT-INDEX directories for different failures:
        # The rest are going to end up in WONT-INDEX for later retry.

        if [ $status -eq 1 ]; then
            echo "$TS: index failures encountered on $result" >&4
            nerrs=$nerrs+1
            echo $result >> $erred
            mkdir -p ${controller_path}/$linkerrdest.$status
            mv $result ${controller_path}/$linkerrdest.$status/
        elif [ $status -eq 2 -o $status -eq 3 ]; then
            echo "$TS: index configuration error $status on $result" >&4
            nerrs=$nerrs+1
            echo $result >> $erred
            mkdir -p ${controller_path}/$linkerrdest.$status
            mv $result ${controller_path}/$linkerrdest.$status/
        elif [ $status -ge 4 -a $status -le 11 ]; then
            # Quietly skip these errors
            nskip=$nskip+1
            echo $result >> $skipped
            mkdir -p ${controller_path}/$linkerrdest.$status
            mv $result ${controller_path}/$linkerrdest.$status/
        else
            echo "$TS: index error $status on $result" >&4
            nerrs=$nerrs+1
            echo $result >> $erred
            mv $result ${controller_path}/$linkerrdest/
        fi
        continue
    fi

    # move the link to $linkdest directory
    # echo mv $result $(echo $result | sed "s/$linksrc/$linkdest/")
    mv $result $(echo $result | sed "s/$linksrc/$linkdest/")
    status=$?
    if [ $status -ne 0 ] ;then
        echo "$TS: Cannot move $result link from $linksrc to $linkdest: code $status" >&4
        nerrs=$nerrs+1
        echo $result >> $erred
        continue
    fi

    # log the success
    echo "$TS: $hostname/$resultname: success"
    nidx=$nidx+1
    echo $result >> $indexed

    # debugging run
    # if (($nidx > 10)) ;then break ;fi
    echo "   $(timestamp): Finished $result (size $size)"
done < $list

echo "$TS: ending at $(timestamp), indexed $nidx (skipped $nskip) results, $nerrs errors"

log_finish

> $report_body

# Tricky quoting: variables are not expanded until the final eval.
# That solved the problem of embedded parens - in the meantime, we got rid of the
# parens, so it has become moot.
if [[ $nerrs > 0 && $nskip > 0 ]] ;then
    subj="$PROG.$TS - Indexed $nidx results, skipped $nskip results, w/ $nerrs errors"
elif [[ $nskip > 0 ]] ;then
    subj="$PROG.$TS - Indexed $nidx results, skipped $nskip results"
elif [[ $nerrs > 0 ]] ;then
    subj="$PROG.$TS($PBENCH_ENV) - Indexed $nidx results, w/ $nerrs errors"
else
    subj="$PROG.$TS($PBENCH_ENV) - Indexed $nidx results"
fi

cat << EOF > $report_body
$subj
EOF
if [[ $nidx -gt 0 ]]; then
    echo
    echo "Indexed Results"
    echo "==============="
    cat $indexed
fi  >> $report_body
if [[ $nerrs -gt 0 ]]; then
    echo
    echo "Results producing errors"
    echo "========================"
    cat $erred
fi  >> $report_body
if [[ $nskip -gt 0 ]]; then
    echo
    echo "Skipped Results"
    echo "==============="
    cat $skipped
fi  >> $report_body

pbench-report-status --name $PROG --timestamp $TS --type status $report_body

exit 0
