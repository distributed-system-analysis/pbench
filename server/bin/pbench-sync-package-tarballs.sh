#! /bin/bash

# This script collects tarballs in TO-SYNC state and packages
# them up as a single tarball on its standard output.

# *WARNING*: Do not put anything in here that will pollute the
# standard output!

# load common things
. $dir/pbench-base.sh

remotearchive=$ARCHIVE
pushd $remotearchive >/dev/null || exit 1

tmp=$(get-tempdir-name $PROG)

trap "rm -rf $tmp" EXIT
mkdir -p "$tmp" || exit 1

calculate_prefixname () {
    local prefix

    tarname=${1##*/}
    prefixname=${tarname%%.tar.xz}
    despath=${1%/*}
    prefixpath=".prefix/$prefixname.prefix"
    prefix="$despath/$prefixpath"
    echo $prefix
}

calculate_md5_prefix () {
    local tar_list

    tar_list="$@"
    for tar in ${tar_list[@]}; do
        if [ -s $remotearchive/$tar ]; then
            if [[ -s $remotearchive/$tar.md5 ]]; then
                echo "$tar"
                echo "$tar.md5"
            else
                echo Failed: "$remotearchive/$tar" exist but "$remotearchive/$tar.md5" not exist >&4
            fi
            prefix=$(calculate_prefixname $tar)
            if [ -s $remotearchive/$prefix ]; then
                echo "$prefix"
            fi
        else
            echo Failed: "$remotearchive/$tar" not exist >&4
        fi
    done
}

log_init $PROG

tar_list=$(find . -path '*/TO-SYNC/*.tar.xz' -printf '%P\n' | sed 's/\/TO-SYNC//g' | sort)
calculate_md5_prefix $tar_list > $tmp/files-to-sync

# package everything and use the saved stdout (see log_init)
tar cf - -T $tmp/files-to-sync >&100
status=$?
if [[ $status != 0 ]] ;then
    log_exit "$TS: Failed: tar --create -T $tmp/files-to-sync"
fi

log_finish

# do not report anything here: pbench-sync-satellite on the master
# will do all the reporting necessary.

exit 0
