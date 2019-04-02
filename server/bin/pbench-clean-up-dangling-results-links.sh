#! /bin/bash

# clean up dangling links from $RESULTS

# load common things
. $dir/pbench-base.sh

# check that all the directories exist
test -d $ARCHIVE || doexit "Bad ARCHIVE=$ARCHIVE"
test -d $RESULTS || doexit "Bad RESULTS=$RESULTS"

cd $RESULTS || doexit "cd $RESULTS failed"

log_init $PROG

for x in $(find . -type l) ; do
     y=$(readlink $x)
     if [ ! -d $y ] ;then
        hostname=$(basename $(dirname $y))
        pbench_run_name=$(basename $y)
        if [ -f $ARCHIVE/$hostname/$pbench_run_name.tar.xz ] ;then
            echo "$x -> $y dangling and $hostname/$pbench_run_name.tar.xz exists - cleaning up the link"
            rm -f $x
        else
            echo "$x -> $y dangling and $hostname/$pbench_run_name.tar.xz does *NOT* exist" >&4
        fi
     fi
done

log_finish
exit 0
