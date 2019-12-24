#! /bin/bash
# set -x

# This shim is used to prepare the tarballs that a version 002 client
# submits for further processing. It copies the tarballs and their MD5
# sums to the archive (after checking) and sets the state links, so
# that the dispatch script will pick them up and get the ball
# rolling. IOW, it does impedance matching between version 002 clients
# and the server scripts.

# load common things
. $dir/pbench-base.sh

test -d $ARCHIVE || doexit "Bad ARCHIVE=$ARCHIVE"

errlog=$LOGSDIR/$PROG/$PROG.error
mkdir -p $LOGSDIR/$PROG
sts=$?
if [ $sts != 0 ]; then
    echo "Failed: \"mkdir -p $LOGSDIR/$PROG\", status $sts" >> $errlog
    exit 1
fi

qdir=$(getconf.py pbench-quarantine-dir pbench-server)
if [ -z "$qdir" ] ;then
    echo "Failed: \"getconf.py pbench-quarantine-dir pbench-server\", status $sts" >> $errlog
    exit 2
fi
if [ ! -d "$qdir" ] ;then
    echo "Failed: $qdir does not exist, or is not a directory" >> $errlog
    exit 2
fi

# we are explicitly handling version-002 data in this shim
receive_dir_prefix=$(getconf.py pbench-receive-dir-prefix pbench-server)
if [ -z "$receive_dir_prefix" ] ;then
    echo "Failed: \"getconf.py pbench-receive-dir-prefix pbench-server\", status $sts" >> $errlog
    exit 2
fi
receive_dir=${receive_dir_prefix}-002
if [ ! -d "$receive_dir" ] ;then
    echo "Failed: $receive_dir does not exist, or is not a directory" >> $errlog
    exit 2
fi

quarantine=${qdir}/md5-002
mkdir -p ${quarantine}
sts=$?
if [ $sts != 0 ]; then
    echo "Failed: \"mkdir -p ${quarantine}\", status $sts" >> $errlog
    exit 3
fi

duplicates=${qdir}/duplicates-002
mkdir -p ${duplicates}
sts=$?
if [ $sts != 0 ]; then
    echo "Failed: \"mkdir -p ${duplicates}\", status $sts" >> $errlog
    exit 3
fi

# The following directory holds tarballs that are quarantined because
# of operational errors on the server. They should be retried after
# the problem is fixed: basically, move them back into the reception
# area for 002 agents and wait.
errors=${qdir}/errors-002
mkdir -p ${errors}
sts=$?
if [ $sts != 0 ]; then
    echo "Failed: \"mkdir -p ${errors}\", status $sts" >> $errlog
    exit 3
fi

log_init $PROG

tmp=$TMP/$PROG.$$

trap 'rm -rf $tmp' EXIT INT QUIT

mkdir -p $tmp
sts=$?
if [ $sts != 0 ]; then
    log_exit "Failed: \"mkdir -p $tmp\", status $sts" 4
fi

list=$tmp/list.check
status=$tmp/status
> $status

echo $TS
# Check for results that are ready for processing: version 002 agents
# upload the MD5 file as xxx.md5.check and they rename it to xxx.md5
# after they are done with MD5 checking so that's what we look for.
find ${receive_dir} -maxdepth 2 -name '*.tar.xz.md5' > ${list}.unsorted
sts=$?
if [ $sts != 0 ] ;then
    log_exit "Failed: \"find ${receive_dir} -maxdepth 2 -name '*.tar.xz.md5'\", status $sts" 5
fi
sort ${list}.unsorted > ${list}
sts=$?
if [ $sts != 0 ] ;then
    log_exit "Failed: \"sort ${list}.unsorted > ${list}\", status $sts" 6
fi

typeset -i ntotal=0
typeset -i ntbs=0
typeset -i nerrs=0
typeset -i nquarantined=0
typeset -i ndups=0

while read tbmd5 ;do
    ntotal=$ntotal+1
    # full pathname of tarball
    tb=${tbmd5%.md5}

    # directory
    tbdir=$(dirname ${tb})

    # resultname: get the basename foo.tar.xz and then strip the .tar.xz
    resultname=$(basename ${tb})
    resultname=${resultname%.tar.xz}

    # the controller hostname is the last component of the directory part of the full path
    controller=$(basename ${tbdir})

    dest=${ARCHIVE}/${controller}

    if [ -f ${dest}/${resultname}.tar.xz -o -f ${dest}/${resultname}.tar.xz.md5 ] ;then
        echo "$TS: Duplicate: ${tb} duplicate name" >&4
        quarantine ${duplicates}/${controller} ${tb} ${tbmd5}
        ndups=$ndups+1
        continue
    fi

    pushd ${tbdir} > /dev/null 2>&4
    md5sum --check ${resultname}.tar.xz.md5
    sts=$?
    popd > /dev/null 2>&4
    if [ $sts -ne 0 ] ;then
        echo "$TS: Quarantined: ${tb} failed MD5 check" >&4
        quarantine ${quarantine}/${controller} ${tb} ${tb}.md5
        nquarantined=$nquarantined+1
        continue
    fi

    # make the destination directory and its TODO subdir if necessary.
    mkdir -p ${dest}/TODO
    sts=$?
    if [ $sts -ne 0 ] ;then
        echo "$TS: Error: \"mkdir -p ${dest}/TODO\", status $sts" |
            tee -a $status >&4
        quarantine ${errors}/${controller} ${tb} ${tb}.md5
        nerrs=$nerrs+1
        continue
    fi

    cp ${tb} ${tb}.md5 ${dest}/
    sts=$?
    if [ $sts -ne 0 ] ;then
        echo "$TS: Error: \"cp ${tb} ${tb}.md5 ${dest}/\", status $sts" |
            tee -a $status >&4
        rm -f ${dest}/${resultname}.tar.xz ${dest}/${resultname}.tar.xz.md5
        sts=$?
        if [ $sts -ne 0]; then
            echo "$TS: Warning: cleanup of copy failure failed itself: \"rm -f ${dest}/${resultname}.tar.xz ${dest}/${resultname}.tar.xz.md5\", status $sts" |
                tee -a $status >&4
        fi
        quarantine ${errors}/${controller} ${tb} ${tb}.md5
        nerrs=$nerrs+1
        continue
    fi
    rm -f ${tb} ${tb}.md5
    sts=$?
    if [ $sts -ne 0 ] ;then
        echo "$TS: Warning: cleanup of successful copy operation failed: \"rm -f ${tb} ${tb}.md5\", status $sts" |
            tee -a $status >&4
    fi

    ln -s ${dest}/${resultname}.tar.xz ${dest}/TODO/
    sts=$?
    if [ $sts -ne 0 ] ;then
        echo "$TS: Error: \"ln -s ${dest}/${resultname}.tar.xz ${dest}/TODO/\", status $sts" |
            tee -a $status >&4
        # if we fail to make the link, we quarantine the (already moved)
        # tarball and .md5.
        quarantine ${errors}/${controller} ${dest}/${tb} ${dest}/${tb}.md5
        nerrs=$nerrs+1
    else
        echo "$TS: processed ${tb}" >> $status
        ntbs=$ntbs+1
    fi
done < $list

echo "$TS: Processed $ntotal entries, $ntbs tarballs successful,"\
     "$nquarantined quarantined tarballs, $ndups duplicately-named tarballs,"\
     "$nerrs errors." | tee -a $status

log_finish

pbench-report-status --name ${PROG} --pid ${$} --timestamp $(timestamp) --type status ${status}

exit $nerrs
