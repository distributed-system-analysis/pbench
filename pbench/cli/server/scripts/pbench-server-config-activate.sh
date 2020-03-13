#! /bin/bash
# -*- mode: shell-script -*-

prog=$(basename $0)
usage="$prog <config file path>"

case $# in
    1)
        configfile=$1
        ;;
    *)
        echo $usage
        exit 1
        ;;
esac

if [ ! -f $configfile ] ;then
    echo "$prog: $configfile does not exist"
    exit 2
fi

configdir=$(dirname $configfile)
config_files=$(ls $configdir)
# copy the configuration file to the standard place
dest=$(getconf.py --config $configfile install-dir pbench-server)
dest=$dest/lib/config

for x in $config_files ;do
    #echo "cp $configdir/$x $dest"
    cp $configdir/$x $dest/
    rc=$?
    if [ $rc -gt 0 ] ;then
        echo "$prog: unable to copy config file $configdir/$x to $dest/, code: $rc"
        exit 3
    fi
done

user=$(getconf.py --config $configfile user pbench-server)
if [ -z "$user" ] ;then
    echo "$prog: user is undefined in section \"pbench-server\" of config file."
    exit 4
fi

group=$(getconf.py --config $configfile group pbench-server)
if [ -z "$group" ] ;then
    echo "$prog: group is undefined in section \"pbench-server\" of config file."
    exit 5
fi

chown -R $user.$group $dest
rc=$?
if [ $rc -gt 0 ]; then
    echo "$prog: chown -R $user.$group $dest failed, code: $rc"
    exit 6
fi

exit 0
