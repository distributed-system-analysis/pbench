#! /bin/bash

# set -x

# This shim is used to prepare the tarballs that a version 001 client
# submits for further processing. It copies the tarballs and their MD5
# sums (plus an optional prefix file) to the archive (after checking)
# and sets the state links, so that the dispatch script will pick them
# up and get the ball rolling. IOW, it does impedance matching between
# version 001 clients and the server scripts.

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

# we are explicitly handling version-001 data in this shim
receive_dir_prefix=$(getconf.py pbench-receive-dir-prefix pbench-server)
if [ -z "$receive_dir_prefix" ] ;then
    echo "Failed: \"getconf.py pbench-receive-dir-prefix pbench-server\", status $sts" >> $errlog
    exit 2
fi
receive_dir=${receive_dir_prefix}-001
if [ ! -d "$receive_dir" ] ;then
    echo "Failed: $receive_dir does not exist, or is not a directory" >> $errlog
    exit 2
fi

quarantine=${qdir}/md5-001
mkdir -p ${quarantine}
sts=$?
if [ $sts != 0 ]; then
    echo "Failed: \"mkdir -p ${quarantine}\", status $sts" >> $errlog
    exit 3
fi

duplicates=${qdir}/duplicates-001
mkdir -p ${duplicates}
sts=$?
if [ $sts != 0 ]; then
    echo "Failed: \"mkdir -p ${duplicates}\", status $sts" >> $errlog
    exit 3
fi

# The following directory holds tarballs that are quarantined because
# of operational errors on the server. They should be retried after
# the problem is fixed: basically, move them back into the reception
# area for 001 agents and wait.
errors=${qdir}/errors-001
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
    echo "Failed: \"mkdir -p $tmp\", status $sts" >> $errlog
    log_finish
    exit 4
fi

list=$tmp/list.tb
status=$tmp/status
> $status

echo $TS

# Check for results that are ready for processing: version 001
# agents create a link in the TODO subdir (which is created if
# necessary) after they finish with MD5 checking, so that's what
# we look for.
> ${list}.unsorted
# First we find all the TODO directories
for todo_dir in $(find ${receive_dir}/ -maxdepth 2 -type d -name TODO 2>/dev/null); do
    # Find all the links in a given TODO directory that are
    # links to actual files (bad links are not emitted!).
    find -L $todo_dir -type f -name '*.tar.xz' -printf "%p\n" 2>/dev/null >> ${list}.unsorted
    # Find all the links in the same TODO directory that don't
    # link to anything so that we can count them as errors below.
    find -L $todo_dir -type l -name '*.tar.xz' -printf "%p\n" 2>/dev/null >> ${list}.unsorted
done
sort ${list}.unsorted > ${list}
rm -f ${list}.unsorted

typeset -i ntotal=0
typeset -i ntbs=0
typeset -i nerrs=0
typeset -i nquarantined=0
typeset -i ndups=0

while read tblink ;do
    ntotal=$ntotal+1
    # resolve the link
    tb=$(readlink -e ${tblink})
    sts=$?
    if [ $sts != 0 ] ;then
        echo "$TS: readlink -e ${tblink} failed: $sts" | tee -a $status >&4
        nerrs=$nerrs+1
        quarantine ${qdir}/__BAD_TODO_LINKS ${tblink}
        continue
    fi

    # directory
    tbdir=$(dirname ${tb})

    # resultname: get the basename foo.tar.xz and then strip the .tar.xz
    resultname=$(basename ${tb})
    resultname=${resultname%.tar.xz}

    # hostname is the last component of the directory part of the full path
    controller=$(basename ${tbdir})

    dest=$ARCHIVE/${controller}

    # Rename any prefix file now, so if we run into problems,
    # we quarantine it with the new name.
    prefix=""
    # if necessary, fix prefix file name.
    if [ -f "${tbdir}/prefix.${resultname}" ] ;then
        # rename it - using a prefix form was a mistake.
        mv ${tbdir}/prefix.${resultname} ${tbdir}/${resultname}.prefix
        sts=$?
        if [ $sts -ne 0 ] ;then
            # If the mv fails, we still want to do the rest of the pipeline,
            # although we might have to fix up the results/controlle/prefix link
            # manually.
            echo "$TS: Warning: mv ${tbdir}/prefix.${resultname} ${tbdir}/${resultname}.prefix failed - ignoring" >&4
        fi
    fi
    # ... and remember it
    if [ -f "${tbdir}/${resultname}.prefix" ] ;then
        prefix="${tbdir}/${resultname}.prefix"
    fi

    # version 001 agents check for duplicates in pbench-move-results but the check
    # is almost completely ineffective now, since they can't see the "real" archive
    # directory where the tarballs are stored. They will only be able to see any
    # duplicates in the reception area and only during the short time before this
    # script gets to them and moves them.
    if [ -f ${dest}/${resultname}.tar.xz -o -f ${dest}/${resultname}.tar.xz.md5 ] ;then
        echo "$TS: Duplicate: ${tb}" >&4
        quarantine $duplicates/$controller ${tb} ${tb}.md5 ${prefix}
        rm -f ${tblink}
        ndups=$ndups+1
        continue
    fi

    pushd ${tbdir} > /dev/null 2>&4
    md5sum --check ${resultname}.tar.xz.md5
    sts=$?
    popd > /dev/null 2>&4
    if [ $sts -ne 0 ] ;then
        echo "$TS: Quarantined: ${tb} failed MD5 check" >&4
        quarantine ${quarantine}/${controller} ${tb} ${tb}.md5 ${prefix}
        rm -f ${tblink}
        nquarantined=${nquarantined}+1
        continue
    fi

    # make the destination directory and its TODO subdir if necessary.
    mkdir -p ${dest}/TODO
    sts=$?
    if [ $sts -ne 0 ] ;then
        echo "$TS: Error: \"mkdir -p ${dest}/TODO\", status $sts" |
            tee -a $status >&4
        quarantine ${errors}/${controller} ${tb} ${tb}.md5 ${prefix}
        rm -f ${tblink}
        nerrs=$nerrs+1
        continue
    fi

    # move the prefix file first, if present
    if [ ! -z "${prefix}" ] ;then
        mkdir -p ${dest}/.prefix > /dev/null 2>&1
        mv ${prefix} ${dest}/.prefix/
        sts=$?
        if [ $sts -ne 0 ] ;then
            echo "$TS: Error: \"mv ${prefix} ${dest}/.prefix/\", status $sts" |
                tee -a $status >&4
            quarantine ${errors}/${controller} ${tb} ${tb}.md5 ${prefix}
            rm -f ${tblink}
            nerrs=$nerrs+1
            continue
        fi
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
        quarantine ${errors}/${controller} ${tb} ${tb}.md5 ${dest}/.prefix/${resultname}.prefix
        rm -f ${tblink}
        nerrs=$nerrs+1
        continue
    fi
    rm -f ${tb} ${tb}.md5
    sts=$?
    if [ $sts -ne 0 ] ;then
        echo "$TS: Warning: cleanup of successful copy operation failed: \"rm -f ${tb} ${tb}.md5\", status $sts" |
            tee -a $status >&4
    fi

    # Remove the link from the reception area.  rm -f returns the same
    # exit status as rm, except in the case when $tblink does not
    # exist.
    rm -f $tblink
    sts=$?
    if [ $sts -ne 0 ] ;then
        echo "$TS: Error: \"rm -f $tblink\", status $sts" |
            tee -a $status >&4
        nerrs=$nerrs+1
        # this will continue to give errors every time through
        # so we need a better solution
    fi

    ln -s ${dest}/${resultname}.tar.xz ${dest}/TODO/
    sts=$?
    if [ $sts -ne 0 ] ;then
        if [ ! -z $prefix ] ;then
            prefix=${dest}/${prefix}
        fi
        echo "$TS: Error: \"ln -s ${dest}/${resultname}.tar.xz ${dest}/TODO/\", status $sts" |
            tee -a $status >&4
        # if we fail to make the link, we quarantine the (already moved)
        # tarball, .md5, and .prefix/*.prefix files.
        quarantine ${errors}/${controller} ${dest}/${tb} ${dest}/${tb}.md5 ${dest}/.prefix/${resultname}.prefix
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

pbench-report-status --name $PROG --timestamp $(timestamp) --type status $status

exit $nerrs
